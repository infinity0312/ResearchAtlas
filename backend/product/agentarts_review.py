"""Source-scoped evidence review. Cloud output is a draft, local evidence is authoritative."""

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select

from ..analysis_pipeline import verified_claims
from ..analysis_repository import current_query
from ..db import DATA, Analysis, Paper, Session
from ..research_trace import parsed_source
from ..search import ranked_page, search_filter
from . import agentarts_client, service
from .contracts import EvidenceInput
from .models import AgentArtsReview
from .router import write

router = APIRouter(prefix='/api/projects', tags=['AgentArts 证据评审'])


class StrictInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)


class ApprovedSource(StrictInput):
    analysis_id: int = Field(gt=0)
    pdf_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    parsed_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


class DemoScope(StrictInput):
    projects: list[str] = Field(min_length=1, max_length=10)
    sources: list[ApprovedSource] = Field(min_length=1, max_length=30)


class StartReview(StrictInput):
    revision: int = Field(ge=1)
    query: str = Field(min_length=1, max_length=160)


class Finding(StrictInput):
    evidence_id: str = Field(min_length=1, max_length=32)
    stance: Literal['supports', 'contradicts', 'uncertain']
    reason: str = Field(min_length=4, max_length=700)


class CriterionAssessment(StrictInput):
    criterion_id: str = Field(min_length=1, max_length=60)
    findings: list[Finding] = Field(max_length=6)
    next_step: str = Field(min_length=1, max_length=700)


class ReviewResult(StrictInput):
    assessments: list[CriterionAssessment] = Field(min_length=1, max_length=8)


class BindFinding(StrictInput):
    revision: int = Field(ge=1)
    criterion_id: str = Field(min_length=1, max_length=60)
    evidence_id: str = Field(min_length=1, max_length=32)


def demo_scope():
    filename = os.getenv('ATLAS_AGENTARTS_SCOPE_FILE')
    if not filename:
        return None
    try:
        path = Path(filename)
        if path.stat().st_size > 32_000:
            return None
        scope = DemoScope.model_validate_json(path.read_bytes())
        if len({source.analysis_id for source in scope.sources}) == len(scope.sources):
            return scope
    except (OSError, ValidationError):
        pass
    return None


def same_hash(path, expected):
    try:
        if path.stat().st_size > 64 * 1024 * 1024:
            return False
        with path.open('rb') as file:
            return hashlib.file_digest(file, 'sha256').hexdigest() == expected
    except OSError:
        return False


def approved_claims(s, record, paper, approval):
    if record is None or paper is None or record.version != paper.version:
        return []
    latest = s.scalars(current_query([paper.id], record.domain_id).limit(1)).first()
    if latest is None or latest.id != record.id or record.content_hash != approval.pdf_sha256:
        return []
    view = service.analysis_view(s, record)
    if view is None or view['quality']['freshness'] != 'current':
        return []
    stem = hashlib.sha256(paper.id.encode()).hexdigest()
    if not same_hash(DATA / 'documents' / f'{stem}v{record.version}.pdf', approval.pdf_sha256):
        return []
    if not same_hash(DATA / 'documents' / f'{record.content_hash}.json', approval.parsed_sha256):
        return []
    pages = parsed_source(record.content_hash)
    claims = (record.result or {}).get('claims', [])
    if not pages or not isinstance(claims, list):
        return []
    items = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            continue
        quote, page = claim.get('quote'), claim.get('page')
        if not isinstance(quote, str) or not 12 <= len(quote.strip()) <= 1000 or type(page) is not int:
            continue
        # This slice sends one verbatim excerpt per source. Claims needing
        # additional blocks remain available in the regular project workflow.
        if claim.get('supporting_evidence') or not verified_claims([claim], pages):
            continue
        items.append({
            'analysis_id': record.id, 'claim_index': index, 'paper_id': paper.id,
            'paper_version': record.version, 'title': paper.title, 'pdf_page': page,
            'quote': quote, 'claim_digest': service.digest(claim),
        })
    return items


def select_sources(s, scope, query):
    allowed = {a.analysis_id: a for a in scope.sources}
    records = list(s.scalars(select(Analysis).where(Analysis.id.in_(allowed)).order_by(Analysis.id.desc())))
    papers, _, _ = ranked_page(
        s, search_filter(select(Paper).where(Paper.id.in_({a.paper_id for a in records})), query),
        query, scope='agentarts-demo', page=1, size=6, feed=False, cursor=None,
    )
    pool = []
    for paper in papers:
        per_paper = []
        for record in records:
            if record.paper_id == paper.id:
                per_paper = approved_claims(s, record, paper, allowed[record.id])
                if per_paper:
                    break
        pool.extend(per_paper[:2])
    return [{**item, 'evidence_id': f'e{index}'} for index, item in enumerate(pool, 1)]


def cloud_context(project, sources):
    public_fields = ('evidence_id', 'paper_id', 'paper_version', 'title', 'pdf_page', 'quote')
    return {
        'question': project.question, 'constraints': project.constraints,
        'criteria': project.criteria,
        'sources': [{key: item[key] for key in public_fields} for item in sources],
    }


def checked_assessments(output, criteria, sources):
    try:
        review = (ReviewResult.model_validate_json(output) if isinstance(output, str)
                  else ReviewResult.model_validate(output))
    except ValidationError:
        raise agentarts_client.AgentArtsError('工作流输出不符合评审契约') from None
    rows = {row.criterion_id: row for row in review.assessments}
    if len(rows) != len(review.assessments) or set(rows) != {c['id'] for c in criteria}:
        raise agentarts_client.AgentArtsError('工作流返回了遗漏或未知的评价标准')
    known_ids = {source['evidence_id'] for source in sources}
    result = []
    for criterion in criteria:
        row = rows[criterion['id']]
        ids = [item.evidence_id for item in row.findings]
        if set(ids) - known_ids or len(set(ids)) != len(ids):
            raise agentarts_client.AgentArtsError('工作流使用了重复或不属于本次评审的证据')
        stances = {item.stance for item in row.findings} - {'uncertain'}
        status = {frozenset(): 'insufficient', frozenset({'supports'}): 'supported',
                  frozenset({'contradicts'}): 'contradicted'}.get(frozenset(stances), 'mixed')
        result.append({**row.model_dump(), 'label': criterion['label'], 'status': status})
    return result


def review_view(review, revision):
    if review is None:
        return None
    expired = expired_review(review)
    return {
        'id': review.id, 'state': 'failed' if expired else review.state, 'query': review.query,
        'project_revision': review.project_revision, 'expected_revision': review.expected_revision,
        'stale': review.expected_revision != revision, 'execution_id': review.execution_id,
        'sources': review.sources, 'assessments': review.assessments,
        'bindings': review.bindings, 'error': '上一次评审未完成，请重新发起' if expired else review.error,
        'created': review.created,
    }


def latest_review(s, pid):
    return s.scalar(select(AgentArtsReview).where(AgentArtsReview.project_id == pid)
                    .order_by(AgentArtsReview.created.desc(), AgentArtsReview.id.desc()).limit(1))


def expired_review(review):
    return (review.state == 'running'
            and datetime.fromisoformat(review.created) <= datetime.now(timezone.utc) - timedelta(seconds=150))


@router.get('/{pid}/agentarts')
def review_status(pid: str):
    scope = demo_scope()
    if not scope or pid not in scope.projects:
        return {'enabled': False, 'configured': False, 'review': None}
    with Session() as s:
        project = service.project(s, pid)
        return {'enabled': True, 'configured': bool(agentarts_client.configured_runtime()),
                'review': review_view(latest_review(s, pid), project.revision)}


@router.post('/{pid}/agentarts')
def start_review(pid: str, request: StartReview):
    scope = demo_scope()
    if not scope or pid not in scope.projects:
        raise HTTPException(403, '此项目未列入 AgentArts 演示范围')
    runtime = agentarts_client.configured_runtime()
    with Session() as s:
        project = service.project(s, pid, request.revision)
        sources = select_sources(s, scope, request.query)
        context = cloud_context(project, sources)
    if sources and runtime is None:
        raise HTTPException(503, '请先在服务端配置已发布的 AgentArts 工作流')
    with write() as s:
        service.project(s, pid, request.revision)
        previous = latest_review(s, pid)
        if previous is not None and previous.state == 'running':
            if not expired_review(previous):
                raise HTTPException(409, '此项目已有评审在运行')
            previous.state, previous.error = 'failed', '上一次评审未完成，请重新发起'
        run = AgentArtsReview(project_id=pid, project_revision=request.revision,
                              expected_revision=request.revision, query=request.query, sources=sources)
        s.add(run)
        s.flush()
        run_id = run.id
    if sources:
        try:
            output, execution_id = agentarts_client.invoke(runtime, run_id, context)
            assessments = checked_assessments(output, context['criteria'], sources)
            state, error = 'ready', ''
        except agentarts_client.AgentArtsError as exc:
            state, error, execution_id, assessments = 'failed', str(exc), None, []
    else:
        state, error, execution_id = 'no_evidence', '', None
        assessments = [{
            'criterion_id': c['id'], 'label': c['label'], 'findings': [], 'status': 'insufficient',
            'next_step': '调整检索关键词，或将有核对依据的论文加入演示语料。',
        } for c in context['criteria']]
    with write() as s:
        run = s.get(AgentArtsReview, run_id)
        if run.state == 'running':
            run.state, run.error, run.execution_id, run.assessments = state, error, execution_id, assessments
        return review_view(run, service.project(s, pid).revision)


@router.post('/{pid}/agentarts/{run_id}/bind')
def bind_finding(pid: str, run_id: str, request: BindFinding):
    scope = demo_scope()
    if not scope or pid not in scope.projects:
        raise HTTPException(403, '此项目未列入 AgentArts 演示范围')
    with write() as s:
        project = service.project(s, pid)
        run = s.get(AgentArtsReview, run_id)
        if run is None or run.project_id != pid or run.state != 'ready':
            raise HTTPException(404, '没有可采纳的评审草稿')
        key = f'{request.criterion_id}:{request.evidence_id}'
        if key in run.bindings:
            return review_view(run, project.revision)
        if project.revision != request.revision or project.revision != run.expected_revision:
            raise HTTPException(409, '项目修订已变化，请重新发起证据评审')
        row = next((a for a in run.assessments if a['criterion_id'] == request.criterion_id), None)
        finding = next((f for f in row['findings'] if f['evidence_id'] == request.evidence_id), None) if row else None
        source = next((e for e in run.sources if e['evidence_id'] == request.evidence_id), None)
        if not finding or not source or finding['stance'] == 'uncertain':
            raise HTTPException(422, '请选择本次评审中立场明确的依据')
        approved = next((a for a in scope.sources if a.analysis_id == source['analysis_id']), None)
        if approved is None:
            raise HTTPException(409, '来源已移出演示范围')
        current = approved_claims(s, s.get(Analysis, source['analysis_id']), s.get(Paper, source['paper_id']), approved)
        snapshot = {key: value for key, value in source.items() if key != 'evidence_id'}
        if snapshot not in current:
            raise HTTPException(409, '文献版本或证据快照已变化，请重新发起评审')
        attachment = service.attach(s, project, EvidenceInput(
            revision=project.revision, analysis_id=source['analysis_id'], claim_index=source['claim_index'],
            criterion_id=request.criterion_id, stance=finding['stance'], context=finding['reason'],
        ))
        run.bindings = {**run.bindings, key: attachment['id']}
        run.expected_revision = project.revision
        return review_view(run, project.revision)

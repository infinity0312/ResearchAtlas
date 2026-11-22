"""User edits create immutable analysis versions; prior source and reviews survive."""
import copy
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from .db import Analysis, Domain, Paper, Session, now, serialize
from .analysis_repository import current_query, read_analysis, review_certificates, source_updates

router = APIRouter(prefix='/api/analysis')

class EditInput(BaseModel):
    model_config = {'extra': 'forbid'}
    base_analysis_id: int = Field(gt=0)
    summary: str = Field(min_length=1, max_length=20000)
    fulltext_markdown: str = Field(default='', max_length=200000)
    claim_texts: list[str] = Field(max_length=1000)

@router.get('/history')
def history(paper_id: str, domain_id: str, limit: int = Query(30, ge=1, le=100)):
    with Session() as s:
        rows = s.scalars(select(Analysis).where(Analysis.paper_id == paper_id,
            Analysis.domain_id == domain_id).order_by(Analysis.created.desc(), Analysis.id.desc()).limit(limit))
        return [{'id': a.id, 'created': a.created, 'model': a.model, 'version': a.version,
                 'edited': bool(a.result.get('editorial_edit'))} for a in rows]

@router.get('/{analysis_id}/version')
def version(analysis_id: int):
    with Session() as s:
        a = s.get(Analysis, analysis_id)
        if a is None: raise HTTPException(404, '分析版本不存在')
        return serialize(a)

@router.post('/{analysis_id}/edit')
def edit(analysis_id: int, data: EditInput):
    if not data.summary.strip() or any(not t.strip() or len(t) > 20000 for t in data.claim_texts):
        raise HTTPException(422, '摘要和结论不能留空，单条结论不得超过 20000 字')
    with Session.begin() as s:
        if s.bind.dialect.name == 'sqlite': s.connection().exec_driver_sql('BEGIN IMMEDIATE')
        base = s.get(Analysis, analysis_id)
        if base is None: raise HTTPException(404, '分析版本不存在')
        paper = s.get(Paper, base.paper_id); domain = s.get(Domain, base.domain_id)
        current = s.scalar(current_query([base.paper_id], base.domain_id).limit(1))
        if data.base_analysis_id != analysis_id or current is None or current.id != analysis_id:
            raise HTTPException(409, '已有新的分析版本；你的草稿已保留，请查看最新版本后合并')
        if paper is None or domain is None: raise HTTPException(409, '论文或领域已删除')
        updates = source_updates(s, [paper.id])
        reviews = review_certificates(s, [base.id])
        view = read_analysis(base, paper, domain, updates, full=True, independent_review=reviews.get(base.id))
        result = copy.deepcopy(view['result'])
        claims = result.get('claims', [])
        if len(data.claim_texts) != len(claims): raise HTTPException(422, '结论数量已变化，请重新载入')
        if (data.summary == result.get('summary', '') and
            data.fulltext_markdown == result.get('fulltext_markdown', '') and
            data.claim_texts == [c['text'] for c in claims]):
            return view
        # The old certificate approves exact old prose; edits cannot inherit it.
        for key in ('grounding', 'prompt_version', 'field_evidence', 'pipeline_fingerprint', 'quality'):
            result.pop(key, None)
        result.update(summary=data.summary, fulltext_markdown=data.fulltext_markdown,
            claims=[{**c, 'text': text} for c, text in zip(claims, data.claim_texts)],
            editorial_edit={'base_analysis_id': base.id, 'edited_at': now(), 'editor': 'user',
                            'original_model': base.model})
        row = Analysis(paper_id=base.paper_id, domain_id=base.domain_id, version=base.version,
            taxonomy_version=base.taxonomy_version, content_hash=base.content_hash,
            model=base.model, result=result)
        s.add(row); s.flush()
        return read_analysis(row, paper, domain, updates, full=True)

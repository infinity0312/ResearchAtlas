"""Read-only source impact projections and independently versioned shortlists.

All mutations are called inside the router's existing BEGIN IMMEDIATE boundary.
Candidate discovery is deliberately outside the scientific review fingerprint.
"""
from fastapi import HTTPException
from sqlalchemy import func, select

from ..db import Analysis, Domain, Paper, now, serialize
from .models import ProjectCandidate, ProjectEvidence, ResearchProject
from . import service


def criterion_labels(project):
    criteria = project.criteria if isinstance(project.criteria, list) else []
    return {c['id']: c.get('label', c['id']) for c in criteria
            if isinstance(c, dict) and isinstance(c.get('id'), str)}


def candidate_view(s, candidate):
    paper = s.get(Paper, candidate.paper_id)
    available = s.scalar(select(Analysis.id).where(Analysis.paper_id == candidate.paper_id).limit(1))
    bindings = s.scalar(select(func.count()).select_from(ProjectEvidence).where(
        ProjectEvidence.project_id == candidate.project_id,
        ProjectEvidence.paper_id == candidate.paper_id,
    ))
    return {**serialize(candidate), 'current_version': paper.version if paper else None,
            'analysis_available': available is not None, 'binding_count': bindings}


def candidates(s, project):
    items = [candidate_view(s, candidate) for candidate in s.scalars(
        select(ProjectCandidate).where(ProjectCandidate.project_id == project.id)
        .order_by(ProjectCandidate.created, ProjectCandidate.id))]
    return {'items': items, 'total': len(items)}


def add_candidate(s, project, data):
    existing = s.scalar(select(ProjectCandidate).where(
        ProjectCandidate.project_id == project.id, ProjectCandidate.paper_id == data.paper_id))
    if existing is not None:
        return candidate_view(s, existing)
    paper = s.get(Paper, data.paper_id)
    if paper is None:
        raise HTTPException(404, '候选文献不存在')
    candidate = ProjectCandidate(project_id=project.id, paper_id=paper.id,
        title=paper.title, paper_version=paper.version, reason=data.reason)
    s.add(candidate)
    s.flush()
    service.event(s, project, 'candidate_added', {'before': None, 'after': serialize(candidate)})
    return candidate_view(s, candidate)


def edit_candidate(s, project, cid, data):
    candidate = s.get(ProjectCandidate, cid)
    if candidate is None or candidate.project_id != project.id:
        raise HTTPException(404, '项目候选文献不存在')
    if candidate.revision != data.revision:
        raise HTTPException(409, '候选记录已变化，请保留输入并重新载入')
    if candidate.status == data.status and candidate.reason == data.reason:
        return candidate_view(s, candidate)
    before = serialize(candidate)
    candidate.status, candidate.reason = data.status, data.reason
    candidate.revision += 1
    candidate.updated = now()
    s.flush()
    service.event(s, project, 'candidate_updated', {'before': before, 'after': serialize(candidate)})
    return candidate_view(s, candidate)


def paper_links(s, paper_id):
    shortlisted = {row.project_id: row for row in s.scalars(
        select(ProjectCandidate).where(ProjectCandidate.paper_id == paper_id))}
    evidence = list(s.scalars(select(ProjectEvidence).where(ProjectEvidence.paper_id == paper_id)))
    ids = set(shortlisted) | {e.project_id for e in evidence}
    items = []
    if not ids:
        return {'items': items}
    for project in s.scalars(select(ResearchProject).where(ResearchProject.id.in_(ids))
                             .order_by(ResearchProject.updated.desc(), ResearchProject.id)):
        labels = criterion_labels(project)
        bindings = [{'id': e.id, 'criterion_id': e.criterion_id,
            'criterion_label': labels.get(e.criterion_id, e.criterion_id),
            'stance': e.stance, 'eligible': service.evidence_health(s, e)['eligible']}
            for e in evidence if e.project_id == project.id]
        items.append({'project_id': project.id, 'title': project.title,
            'revision': project.revision, 'status': project.status,
            'candidate': candidate_view(s, shortlisted[project.id]) if project.id in shortlisted else None,
            'evidence': bindings})
    return {'items': items}


def impact_kind(s, evidence, health):
    """Classify from source identity and quality fields, never translated messages."""
    analysis = s.get(Analysis, evidence.analysis_id)
    paper = s.get(Paper, evidence.paper_id)
    if analysis is None or paper is None or s.get(Domain, analysis.domain_id) is None:
        return 'source_changed'
    if health['latest_analysis_id'] != evidence.analysis_id:
        return 'source_changed'
    quality = health.get('quality') or {}
    snapshot = evidence.snapshot if isinstance(evidence.snapshot, dict) else {}
    result = analysis.result if isinstance(analysis.result, dict) else {}
    claims = result.get('claims')
    if not isinstance(claims, list) or any(key not in snapshot for key in
            ('paper_version', 'content_hash', 'claim_digest', 'paper_title')):
        return 'source_changed'
    changed = (analysis.version != snapshot['paper_version']
        or paper.version != snapshot['paper_version']
        or analysis.content_hash != snapshot['content_hash']
        or type(evidence.claim_index) is not int
        or evidence.claim_index < 0 or evidence.claim_index >= len(claims))
    if not changed:
        changed = service.digest(claims[evidence.claim_index]) != snapshot['claim_digest']
    return 'source_changed' if changed or quality.get('freshness') != 'current' else 'needs_verification'


def impacts(s):
    items = []
    projects = {p.id: p for p in s.scalars(select(ResearchProject))}
    for evidence in s.scalars(select(ProjectEvidence).order_by(ProjectEvidence.project_id, ProjectEvidence.id)):
        project = projects.get(evidence.project_id)
        if project is None:
            continue
        health = service.evidence_health(s, evidence)
        if health['eligible']:
            continue
        paper = s.get(Paper, evidence.paper_id)
        labels = criterion_labels(project)
        snapshot = evidence.snapshot if isinstance(evidence.snapshot, dict) else {}
        items.append({'project_id': project.id, 'project_title': project.title,
            'project_revision': project.revision, 'evidence_id': evidence.id,
            'paper_id': evidence.paper_id, 'paper_title': snapshot.get('paper_title', '绑定题录缺失'),
            'criterion_id': evidence.criterion_id,
            'criterion_label': labels.get(evidence.criterion_id, evidence.criterion_id),
            'stance': evidence.stance, 'bound_analysis_id': evidence.analysis_id,
            'latest_analysis_id': health['latest_analysis_id'],
            'bound_paper_version': snapshot.get('paper_version'),
            'current_paper_version': paper.version if paper else None,
            'issues': health['issues'], 'kind': impact_kind(s, evidence, health)})
    return {'items': items, 'total': len(items)}

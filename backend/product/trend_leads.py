"""Stored trend projections captured as discovery provenance, without model/network work."""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select

from ..db import Paper, Setting, TrendCount, TrendEvidence, TrendSeries, now, serialize
from ..trend_identity import aliases
from ..trend_signals import insight, period_key, summarize
from ..trends import buckets, key
from .contracts import CandidateCreate
from .models import ProjectTrendLead
from . import research_flow, service


def preview(s, series_id, start, end, interval, period=None, paper_id=None):
    if interval not in ('year', 'month'):
        raise HTTPException(422, '统计间隔必须是year或month')
    try:
        bs = buckets(start, end, interval)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    mapping = aliases(s)
    seen = set()
    while series_id in mapping and series_id not in seen:
        seen.add(series_id)
        series_id = mapping[series_id]
    series = s.get(TrendSeries, series_id)
    if series is None:
        raise HTTPException(404, '趋势方向不存在')
    at = datetime.now(timezone.utc).strftime('%Y%m%d%H%M')
    points = []
    for label, lo, hi in bs:
        cached = s.get(TrendCount, key(series.query, lo, hi))
        points.append({'period': label, 'count': cached.count if cached else None,
            'fetched': cached.fetched if cached else None, 'source': cached.source if cached else None,
            'partial': hi > at})
    complete = [(b, p) for b, p in zip(bs, points) if not p['partial']]
    complete_by_label = {b[0]: b for b, _ in complete}
    if period is not None and period not in complete_by_label:
        raise HTTPException(422, '所选时间点不存在、超出区间或尚未完整')
    selected_period = period if period is not None else (complete[-1][0][0] if complete else None)
    direction = insight(series.query, bs, points)
    selected = {}
    if selected_period is not None:
        _, lo, hi = complete_by_label[selected_period]
        settings = s.get(Setting, 'llm')
        model = settings.value.get('model', '') if settings and isinstance(settings.value, dict) else ''
        evidence = (s.get(TrendEvidence, period_key(series.query, lo, hi, 'codex-source-review'))
                    or s.get(TrendEvidence, period_key(series.query, lo, hi, model)))
        if evidence:
            selected = summarize(evidence.result)
    papers = []
    for entry in selected.get('papers', []):
        local = s.get(Paper, entry['id'])
        item = {field: entry.get(field, '') for field in ('id', 'title', 'quote', 'bottleneck')}
        for field in ('relevant', 'exclusion_reason', 'headroom_quote', 'headroom_source'):
            if field in entry:
                item[field] = entry[field]
        item.update(local_version=local.version if local else None, local_title=local.title if local else None)
        papers.append(item)
    if paper_id is not None and not any(paper['id'] == paper_id and paper.get('relevant', True) is not False
                                         for paper in papers):
        raise HTTPException(422, '焦点论文必须属于所选时间点的相关样本')
    growth = None
    if len(complete) > 1:
        previous, current = complete[-2][1]['count'], complete[-1][1]['count']
        if current is not None and previous not in (None, 0):
            growth = round((current / previous - 1) * 100, 1)
    signal = {field: direction[field] for field in ('x', 'y', 'status', 'rebound')}
    signal['coordinate_basis'] = 'direction_overview'
    for field in ('sample', 'supported_sample', 'population', 'opportunity'):
        if field in selected:
            signal[field] = selected[field]
    snapshot = {'version': 1, 'series_id': series.id, 'name': series.name, 'query': series.query,
        'focus_paper_id': paper_id,
        'scope': {'start': start, 'end': end, 'interval': interval, 'period': selected_period},
        'source': 'arXiv 官方索引 · 全站检索', 'date_basis': '首次提交时间 UTC',
        'points': points, 'growth': growth, 'signal': signal, 'papers': papers}
    return {'source_key': service.digest(snapshot), 'snapshot': snapshot}


def lead_view(s, lead):
    snapshot = lead.snapshot if isinstance(lead.snapshot, dict) else {}
    scope = snapshot.get('scope')
    if not isinstance(scope, dict) or not all(field in scope for field in ('start', 'end', 'interval')):
        return {**serialize(lead), 'source_changed': True, 'current_source_available': False}
    try:
        current = preview(s, snapshot.get('series_id', ''), scope['start'], scope['end'],
                          scope['interval'], scope.get('period'), snapshot.get('focus_paper_id'))
    except HTTPException:
        return {**serialize(lead), 'source_changed': True, 'current_source_available': False}
    return {**serialize(lead), 'source_changed': current['source_key'] != lead.source_key,
            'current_source_available': True}


def create(s, project, data):
    current = preview(s, data.series_id, data.start, data.end, data.interval, data.period, data.focus_paper_id)
    if current['source_key'] != data.source_key:
        raise HTTPException(409, '趋势来源已变化，请保留输入并重新预览')
    existing = s.scalar(select(ProjectTrendLead).where(ProjectTrendLead.project_id == project.id,
                                                       ProjectTrendLead.source_key == data.source_key))
    if existing is not None:
        return lead_view(s, existing)
    allowed = {paper['id']: paper for paper in current['snapshot']['papers']}
    for paper_id in data.paper_ids:
        if paper_id not in allowed or allowed[paper_id].get('relevant', True) is False:
            raise HTTPException(422, '仅允许所选时间点内相关样本文献进入候选清单')
        if s.get(Paper, paper_id) is None:
            raise HTTPException(422, '样本文献尚未收录本地，仅可保留方向线索，不会自动下载')
    mapping = []
    for paper_id in data.paper_ids:
        candidate = research_flow.add_candidate(s, project, CandidateCreate(paper_id=paper_id, reason=data.reason))
        mapping.append({'paper_id': paper_id, 'candidate_id': candidate['id']})
    lead = ProjectTrendLead(project_id=project.id, source_key=data.source_key,
        snapshot=current['snapshot'], reason=data.reason, candidate_ids=mapping)
    s.add(lead)
    s.flush()
    service.event(s, project, 'trend_lead_added', {'before': None, 'after': serialize(lead)})
    return lead_view(s, lead)


def listing(s, project):
    items = [lead_view(s, lead) for lead in s.scalars(select(ProjectTrendLead)
        .where(ProjectTrendLead.project_id == project.id).order_by(ProjectTrendLead.created, ProjectTrendLead.id))]
    return {'items': items, 'total': len(items)}


def edit(s, project, lid, data):
    lead = s.get(ProjectTrendLead, lid)
    if lead is None or lead.project_id != project.id:
        raise HTTPException(404, '项目趋势线索不存在')
    if lead.revision != data.revision:
        raise HTTPException(409, '趋势线索已被修改，请保留输入并重新载入')
    if lead.status == data.status and lead.reason == data.reason:
        return lead_view(s, lead)
    before = serialize(lead)
    lead.status, lead.reason = data.status, data.reason
    lead.revision += 1
    lead.updated = now()
    s.flush()
    service.event(s, project, 'trend_lead_updated', {'before': before, 'after': serialize(lead)})
    return lead_view(s, lead)

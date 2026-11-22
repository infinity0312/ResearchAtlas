"""Version-aware analysis reads and publication guards.

Historical rows remain immutable. A stale model call cannot overwrite a newer
paper/taxonomy/source snapshot, and legacy quality is derived only on reads.
"""
import hashlib
import json

from sqlalchemy import or_, select

from .db import Analysis, DATA, Domain, Paper, Setting, serialize
from .evidence_contracts import PIPELINE_VERSION, quality_for_analysis, valid_grounding


class AnalysisConflict(RuntimeError):
    pass


def provider_fingerprint(provider):
    config = getattr(provider, 'config', {})
    value = [PIPELINE_VERSION, config.get('model'), config.get('base_url'),
             getattr(provider, 'max_tokens', None), getattr(provider, 'system_prompt', None),
             getattr(provider, 'thinking_enabled', False)]
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def find_cached(s, paper, domain, content_hash, provider):
    fingerprint = provider_fingerprint(provider)
    rows = s.scalars(select(Analysis).where(
        Analysis.paper_id == paper.id, Analysis.domain_id == domain.id,
        Analysis.version == paper.version, Analysis.taxonomy_version == domain.taxonomy_version,
        Analysis.content_hash == content_hash, Analysis.model == provider.config['model'],
    ).order_by(Analysis.created.desc(), Analysis.id.desc()))
    return next((row for row in rows if row.result.get('pipeline_fingerprint') == fingerprint
                 and row.result.get('prompt_version') == PIPELINE_VERSION and valid_grounding(row.result)), None)


def current_query(ids=None, domain_id=None):
    query = select(Analysis).join(Paper, Paper.id == Analysis.paper_id).join(Domain, Domain.id == Analysis.domain_id)
    if ids is not None:
        query = query.where(Analysis.paper_id.in_(ids))
    if domain_id:
        query = query.where(Analysis.domain_id == domain_id)
    return query.order_by((Analysis.version == Paper.version).desc(),
                          (Analysis.taxonomy_version == Domain.taxonomy_version).desc(),
                          Analysis.created.desc(), Analysis.id.desc())


class SourceUpdates(dict):
    """Historical redirects plus canonical source hashes for current papers."""
    def __init__(self):
        super().__init__()
        self.current_by_paper = {}


def source_updates(s, ids=None):
    updates = SourceUpdates()
    if ids is not None and not ids:
        return updates
    query = select(Setting).where(or_(Setting.key.like('source-edit:%'),
                                      Setting.key.like('source-redirect:%')))
    if ids is not None:
        query = query.where(Setting.value['paper_id'].as_string().in_(ids))
    rows = list(s.scalars(query))
    # Immutable redirects retain every new predecessor. Legacy source-edit rows
    # only remember the most recent predecessor, so use the current PDF below to
    # recover authoritative freshness even when older redirects never existed.
    for row in sorted(rows, key=lambda r: r.key.startswith('source-edit:')):
        value = row.value
        if not isinstance(value, dict) or not isinstance(value.get('digest'), str):
            continue
        origin = row.key.split(':', 1)[1]
        if origin != value['digest']:
            updates[origin] = value['digest']
        if isinstance(value.get('previous'), str) and value['previous'] != value['digest']:
            updates[value['previous']] = value['digest']
    corrected = [row for row in rows if row.key.startswith('source-edit:')
                 and isinstance(row.value, dict) and isinstance(row.value.get('paper_id'), str)
                 and isinstance(row.value.get('digest'), str)]
    papers = {paper.id: paper for paper in s.scalars(select(Paper).where(
        Paper.id.in_({row.value['paper_id'] for row in corrected})
    ))} if corrected else {}
    pdf_hashes = {}
    for row in corrected:
        value = row.value
        paper = papers.get(value['paper_id'])
        if paper is None:
            continue
        key = (paper.id, paper.version)
        if key not in pdf_hashes:
            path = DATA / 'documents' / (hashlib.sha256(paper.id.encode()).hexdigest() + f'v{paper.version}.pdf')
            try:
                pdf_hashes[key] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                pdf_hashes[key] = None
        original = row.key.removeprefix('source-edit:')
        matches_pdf = pdf_hashes[key] == original
        # New records carry the version; old records without PDF are ambiguous.
        matches_version = pdf_hashes[key] is None and value.get('paper_version') == paper.version
        if matches_pdf or matches_version:
            updates.current_by_paper[key] = value['digest']
    return updates


def effective_hash(content_hash, updates):
    seen = set()
    while content_hash in updates and content_hash not in seen:
        seen.add(content_hash)
        content_hash = updates[content_hash]
    return content_hash


def review_certificates(s, analysis_ids):
    keys = ['analysis-independent-review:' + str(i) for i in analysis_ids]
    return {int(row.key.split(':', 1)[1]): row.value for row in s.scalars(
        select(Setting).where(Setting.key.in_(keys)))} if keys else {}


def read_analysis(analysis, paper, domain, updates, full=False, independent_review=None):
    result = analysis.result or {}
    if independent_review is not None:
        from .independent_review import certificate_result
        result = certificate_result(analysis, independent_review) or result
    item = serialize(analysis) if full else {
        'topics': result.get('topics', []), 'methods': result.get('methods', []),
        'summary': result.get('summary', ''), 'version': analysis.version,
        'taxonomy_version': analysis.taxonomy_version,
    }
    expected = getattr(updates, 'current_by_paper', {}).get((paper.id, paper.version))
    if expected is None:
        expected = effective_hash(analysis.content_hash, updates)
    if full:
        item['result'] = result
    item['quality'] = quality_for_analysis(analysis, paper, domain, expected, independent_review)
    return item


def assert_current(s, paper, domain, content_hash):
    # Refresh can update these exact ORM objects when callers share a Session.
    # Capture expected versions before refreshing rather than compare aliases.
    expected_version = paper.version
    expected_taxonomy = domain.taxonomy_version
    current_paper = s.get(Paper, paper.id, populate_existing=True)
    current_domain = s.get(Domain, domain.id, populate_existing=True)
    if current_paper is None or current_domain is None:
        raise AnalysisConflict('论文或领域已删除；候选缓存保留，未发布结果')
    if current_paper.version != expected_version or current_domain.taxonomy_version != expected_taxonomy:
        raise AnalysisConflict('论文或分类版本已变化；候选缓存保留，请重新分析')
    updates = source_updates(s, [paper.id])
    expected = updates.current_by_paper.get((paper.id, paper.version))
    if expected is None:
        expected = effective_hash(content_hash, updates)
    if expected != content_hash:
        raise AnalysisConflict('解析来源已修订；候选缓存保留，请基于新来源重新分析')

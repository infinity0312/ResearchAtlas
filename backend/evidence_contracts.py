"""Presentation contracts bind every generated field to selected source claims.

Bindings establish traceability, not scientific entailment. Semantic review remains
a separate state even after all quotes and claim references pass validation.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_VERSION = 1
PIPELINE_VERSION = 'evidence-v10-grounded-presentation'


class BoundText(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(min_length=1, max_length=1500)
    claim_indices: list[int] = Field(min_length=1, max_length=15)


class GroundedSynthesis(BaseModel):
    model_config = ConfigDict(extra='forbid')
    summary: list[BoundText] = Field(min_length=1, max_length=8)
    topics: list[BoundText] = Field(default_factory=list, max_length=3)
    methods: list[BoundText] = Field(default_factory=list, max_length=8)
    problems: list[BoundText] = Field(default_factory=list, max_length=5)
    selected_claims: list[int] = Field(min_length=1, max_length=15)


class AnalysisQuality(BaseModel):
    contract_version: Literal[1] = CONTRACT_VERSION
    provenance: Literal['evidence_pipeline', 'legacy'] = 'legacy'
    evidence: Literal['verified', 'partial', 'unverified'] = 'unverified'
    grounding: Literal['bound', 'legacy'] = 'legacy'
    semantic: Literal['not_reviewed', 'model_reviewed', 'human_reviewed'] = 'not_reviewed'
    freshness: Literal['current', 'stale'] = 'current'
    rejected_evidence: int = Field(default=0, ge=0)


def check_synthesis(value, claims, allowed_topics):
    selected = set(value.selected_claims)
    if len(selected) != len(value.selected_claims):
        raise ValueError('selected_claims must be unique')
    if any(i < 0 or i >= len(claims) for i in selected):
        raise ValueError('selected_claims contains invalid index')
    available = {c['kind'] for c in claims}
    represented = {claims[i]['kind'] for i in selected}
    missing = available - represented
    if missing:
        candidates = {k: [i for i, c in enumerate(claims) if c['kind'] == k] for k in sorted(missing)}
        raise ValueError('Include available claim kinds with these indices: ' + str(candidates))
    for field in ('summary', 'topics', 'methods', 'problems'):
        for item in getattr(value, field):
            if not set(item.claim_indices) <= selected or len(set(item.claim_indices)) != len(item.claim_indices):
                raise ValueError(field + ': claim_indices must be unique selected claim indices')
            if field == 'topics' and item.text not in allowed_topics:
                raise ValueError('topics must match an allowed topic exactly')
            if field == 'methods' and not any(claims[i]['kind'] == 'method' for i in item.claim_indices):
                raise ValueError('methods must bind at least one method claim')


def quality_for_analysis(analysis, paper, domain=None, source_hash=None, independent_review=None):
    """Read legacy records conservatively without rewriting historical snapshots."""
    result = analysis.result or {}
    reviewed = False
    if independent_review is not None:
        from .independent_review import certificate_result
        view = certificate_result(analysis, independent_review)
        if view is not None:
            result = view
            reviewed = True
    rejected = result.get('rejected_evidence', 0)
    rejected = rejected if type(rejected) is int and rejected >= 0 else 0
    # Only this pipeline's versioned contract claims reference binding. Model names,
    # generic provenance and user-provided flags never imply scientific review.
    bound = result.get('prompt_version') == PIPELINE_VERSION and valid_grounding(result)
    stale = analysis.version != paper.version
    if domain is not None:
        stale = stale or analysis.taxonomy_version != domain.taxonomy_version
    if source_hash is not None:
        stale = stale or analysis.content_hash != source_hash
    return AnalysisQuality(
        provenance='evidence_pipeline' if bound else 'legacy',
        evidence=('partial' if rejected else 'verified') if bound else 'unverified',
        grounding='bound' if bound else 'legacy',
        semantic='model_reviewed' if reviewed and bound else 'not_reviewed',
        freshness='stale' if stale else 'current',
        rejected_evidence=rejected,
    ).model_dump()


def valid_grounding(result):
    if not isinstance(result, dict):
        return False
    claims = result.get('claims') or []
    if not isinstance(claims, list) or not claims or any(
        not isinstance(c, dict) or not isinstance(c.get('id'), str) or not c['id'].strip()
        for c in claims
    ):
        return False
    ids = {c['id'] for c in claims}
    if len(ids) != len(claims):
        return False
    grounding = result.get('grounding')
    if not isinstance(grounding, dict):
        return False
    for field in ('summary', 'topics', 'methods', 'problems'):
        entries = grounding.get(field)
        if not isinstance(entries, list):
            return False
        values = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get('text'), str) or not entry['text'].strip():
                return False
            refs = entry.get('claim_ids')
            if not isinstance(refs, list) or not refs or any(not isinstance(r, str) or r not in ids for r in refs):
                return False
            if len(set(refs)) != len(refs):
                return False
            values.append(entry['text'])
        expected = '\n\n'.join(values) if field == 'summary' else values
        if result.get(field) != expected:
            return False
    return bool(grounding['summary'])

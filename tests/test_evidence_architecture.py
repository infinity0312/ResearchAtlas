import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.analysis import analyze_document, verified_claims
from backend.app import app
from backend.db import Analysis, Domain, Paper, Session, Setting, now
from backend.evidence_contracts import GroundedSynthesis, check_synthesis, quality_for_analysis, valid_grounding
from backend.analysis_repository import AnalysisConflict, assert_current, find_cached, provider_fingerprint


PAGE = {'page': 1, 'text': 'We propose a graph network. Evaluation uses only molecular data.'}
GOOD = {'kind': 'method', 'text': '使用图网络', 'page': 1, 'quote': 'We propose a graph network.'}
BAD = {'kind': 'contribution', 'text': '取得全部任务最优结果', 'page': 1, 'quote': 'We beat all baselines on all tasks.'}
DOMAIN = SimpleNamespace(name='Test', topics=['Prediction'])


class Fake:
    config = {'model': 'fixture', 'base_url': 'https://fixture.invalid'}
    def __init__(self, values):
        self.values = iter(values)
        self.prompts = []
    def generate(self, prompt):
        self.prompts.append(prompt)
        return next(self.values)


def extraction(**extra):
    return {'summary': 'UNSUPPORTED_SUMMARY', 'topics': ['Prediction'], 'methods': ['UNSUPPORTED_METHOD'],
            'problems': ['UNSUPPORTED_PROBLEM'], 'claims': [GOOD, BAD], **extra}


def synthesis(**extra):
    return {'summary': [{'text': '使用图网络', 'claim_indices': [0]}],
            'topics': [{'text': 'Prediction', 'claim_indices': [0]}],
            'methods': [{'text': '图网络', 'claim_indices': [0]}], 'selected_claims': [0], **extra}


def seed(result, version=1, taxonomy=1):
    with Session.begin() as s:
        s.add(Paper(id='p1', title='Fixture', abstract='Fixture', published=now(), updated=now(), version=1))
        row = Analysis(paper_id='p1', domain_id='molecules', version=version, taxonomy_version=taxonomy,
                       model='fixture', content_hash='old-source', result=result)
        s.add(row)
        s.flush()
        return row.id


def test_rejected_claim_cannot_leak_via_any_presentation_field():
    provider = Fake([extraction(field_evidence={'summary': [0, 1], 'methods.0': [1], 'topics.0': [1], 'problems.0': [1]})])
    result = analyze_document([PAGE], DOMAIN, model=provider)
    assert result['summary'] == GOOD['text']
    assert result['methods'] == [GOOD['text']]
    assert result['topics'] == result['problems'] == []
    assert result['quality']['evidence'] == 'partial'
    assert result['quality']['semantic'] == 'not_reviewed'
    assert valid_grounding(result)
    assert 'UNSUPPORTED' not in json.dumps(result)


def test_single_segment_synthesis_receives_only_verified_claims():
    provider = Fake([extraction(), synthesis()])
    result = analyze_document([PAGE], DOMAIN, model=provider, synthesize=True)
    assert len(provider.prompts) == 2
    assert all(text not in provider.prompts[1] for text in ('UNSUPPORTED_', BAD['text'], BAD['quote']))
    assert result['summary'] == GOOD['text'] and valid_grounding(result)


def test_out_of_range_or_unselected_presentation_binding_is_repaired():
    provider = Fake([extraction(), synthesis(methods=[{'text': 'Wrong', 'claim_indices': [5]}]), synthesis()])
    result = analyze_document([PAGE], DOMAIN, model=provider, synthesize=True)
    assert len(provider.prompts) == 3 and result['methods'] == ['图网络']
    assert 'claim_indices' in provider.prompts[2]


def test_failed_binding_never_returns_publishable_result():
    bad = synthesis(summary=[{'text': 'Wrong', 'claim_indices': [99]}])
    with pytest.raises(ValueError, match='未通过校验'):
        analyze_document([PAGE], DOMAIN, model=Fake([extraction(), bad, bad, bad]), synthesize=True)


def test_method_labels_require_a_method_claim_and_topics_exact_match():
    claims = [{**GOOD, 'kind': 'contribution'}]
    with pytest.raises(ValueError, match='method claim'):
        check_synthesis(GroundedSynthesis.model_validate(synthesis()), claims, DOMAIN.topics)
    value = synthesis(topics=[{'text': 'Unknown', 'claim_indices': [0]}], methods=[])
    with pytest.raises(ValueError, match='allowed topic'):
        check_synthesis(GroundedSynthesis.model_validate(value), [GOOD], DOMAIN.topics)


def test_split_page_quote_map_retains_all_page_pieces():
    assert verified_claims([GOOD], [{'page': 1, 'text': PAGE['text']}, {'page': 1, 'text': 'Appendix text.'}]) == [GOOD]


def test_legacy_quality_never_inferred_from_model_name_or_user_flags():
    legacy = SimpleNamespace(result={'quality': {'semantic': 'human_reviewed', 'evidence': 'verified'}},
                             model='Codex source-reviewed', version=1, taxonomy_version=1, content_hash='hash')
    q = quality_for_analysis(legacy, SimpleNamespace(version=1), SimpleNamespace(taxonomy_version=1))
    assert q['provenance'] == 'legacy' and q['semantic'] == 'not_reviewed' and q['evidence'] == 'unverified'


def test_api_reports_source_staleness_without_rewriting_history():
    result = analyze_document([PAGE], DOMAIN, model=Fake([extraction(), synthesis()]), synthesize=True)
    aid = seed(result)
    with Session.begin() as s:
        s.add(Setting(key='source-edit:old-source', value={'digest': 'new-source', 'paper_id': 'p1'}))
    client = TestClient(app)
    detail = client.get('/api/paper?id=p1').json()['analysis']
    listed = client.get('/api/papers?days=0').json()['items'][0]['analysis']
    assert detail['quality']['freshness'] == listed['quality']['freshness'] == 'stale'
    assert detail['quality']['semantic'] == 'not_reviewed'
    with Session() as s:
        assert s.get(Analysis, aid).result == result


def test_current_analysis_preferred_to_newer_stale_row():
    aid = seed({'summary': 'Current', 'topics': [], 'methods': []})
    with Session.begin() as s:
        s.add(Analysis(paper_id='p1', domain_id='molecules', version=2, taxonomy_version=1,
                       model='fixture', content_hash='hash', result={'summary': 'Stale', 'topics': [], 'methods': []}))
    assert TestClient(app).get('/api/paper?id=p1').json()['analysis']['id'] == aid


def test_cache_identity_includes_provider_configuration_and_revalidates_grounding():
    provider = Fake([extraction(), synthesis()])
    result = analyze_document([PAGE], DOMAIN, model=provider, synthesize=True)
    result['pipeline_fingerprint'] = provider_fingerprint(provider)
    aid = seed(result)
    with Session() as s:
        paper, domain = s.get(Paper, 'p1'), s.get(Domain, 'molecules')
        assert find_cached(s, paper, domain, 'old-source', provider).id == aid
        changed = SimpleNamespace(config={**provider.config, 'base_url': 'https://changed.invalid'})
        assert find_cached(s, paper, domain, 'old-source', changed) is None
    with Session.begin() as s:
        a = s.get(Analysis, aid)
        a.result = {**a.result, 'summary': 'Changed without evidence binding'}
    with Session() as s:
        assert find_cached(s, s.get(Paper, 'p1'), s.get(Domain, 'molecules'), 'old-source', provider) is None


def test_publication_guard_rejects_taxonomy_change_during_generation():
    seed({})
    with Session() as s:
        paper, domain = s.get(Paper, 'p1'), s.get(Domain, 'molecules')
    with Session.begin() as s:
        s.get(Domain, 'molecules').taxonomy_version = 2
    with Session() as s, pytest.raises(AnalysisConflict):
        assert_current(s, paper, domain, 'old-source')

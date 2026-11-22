import copy
import hashlib
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.contracts import Extraction
from backend.db import Analysis, DATA, Paper, Session, Setting, now
from backend.evidence_contracts import quality_for_analysis
from backend.independent_review import FACETS, ReviewReceipt, make_certificate, text_hash

QUOTE = 'We propose a verified molecular model.'
PAGES = [{'page': 1, 'text': QUOTE}]
REPORT = '# Scientific source review\n\n' + 'Detailed source interpretation. ' * 50


def fixture():
    raw = json.dumps({'summary': 'Verified', 'methods': ['Model'], 'topics': [], 'problems': [],
                     'claims': [{'kind': 'method', 'text': 'Method', 'page': 1, 'quote': QUOTE}],
                     'field_evidence': {'summary': [0], 'methods.0': [0]}})
    content = b'%PDF-reviewed-fixture'
    content_hash = hashlib.sha256(content).hexdigest()
    result = {**Extraction.model_validate_json(raw).model_dump(), 'fulltext_markdown': REPORT,
              'provenance': {'generation_model': 'gpt-6.1-sol'}}
    analysis = SimpleNamespace(id=1, content_hash=content_hash, result=result, version=1, taxonomy_version=1)
    receipt = {'decision': 'approved', 'blocking_issues': [], 'reviewer_model': 'gpt-6.1-sol',
               'reviewer_agent': '/peer', 'report_sha256': text_hash(REPORT),
               'result_sha256': text_hash(raw), 'content_hash': content_hash, 'reviewed_pages': [1],
               'checks': {name: {'status': 'passed', 'note': 'Source-bound fixture decision.'} for name in FACETS}}
    coordinator = {**receipt, 'reviewer_agent': '/root', 'reviewer_model': 'codex'}
    return analysis, raw, receipt, coordinator, content


def test_exact_review_changes_quality_without_changing_original_analysis():
    analysis, raw, peer, coordinator, _ = fixture()
    original = copy.deepcopy(analysis.result)
    certificate = make_certificate(analysis, PAGES, raw, '/author', ReviewReceipt(**peer), ReviewReceipt(**coordinator))
    quality = quality_for_analysis(analysis, SimpleNamespace(version=1), independent_review=certificate)
    assert quality['evidence'] == 'verified' and quality['grounding'] == 'bound'
    assert quality['semantic'] == 'model_reviewed'
    assert analysis.result == original
    analysis.result['summary'] = 'Unreviewed amendment'
    assert quality_for_analysis(analysis, SimpleNamespace(version=1), independent_review=certificate)['semantic'] == 'not_reviewed'


@pytest.mark.parametrize('change', ['report', 'raw', 'source', 'author', 'facet', 'page', 'blocked'])
def test_mismatched_or_self_review_never_approves(change):
    analysis, raw, peer, coordinator, _ = fixture()
    if change == 'report': analysis.result['fulltext_markdown'] += ' Changed'
    elif change == 'raw': raw += ' '
    elif change == 'source': peer['content_hash'] = 'f' * 64
    elif change == 'author': peer['reviewer_agent'] = '/author'
    elif change == 'facet': peer['checks']['mathematics']['status'] = 'failed'
    elif change == 'page': peer['reviewed_pages'] = [2]
    elif change == 'blocked': peer['blocking_issues'] = ['Needs correction']
    with pytest.raises(ValueError):
        make_certificate(analysis, PAGES, raw, '/author', ReviewReceipt(**peer), ReviewReceipt(**coordinator))


def test_unbound_field_needs_explicit_addition_and_review_note():
    analysis, raw, peer, coordinator, _ = fixture()
    value = json.loads(raw); value['field_evidence'].pop('methods.0')
    raw = json.dumps(value); analysis.result['field_evidence'] = value['field_evidence']
    peer['result_sha256'] = coordinator['result_sha256'] = text_hash(raw)
    args = (analysis, PAGES, raw, '/author', ReviewReceipt(**peer), ReviewReceipt(**coordinator))
    with pytest.raises(ValueError, match='缺少有效依据'):
        make_certificate(*args)
    with pytest.raises(ValueError, match='人工核查'):
        make_certificate(*args, binding_additions={'methods.0': [0]})
    certificate = make_certificate(*args, binding_additions={'methods.0': [0]}, binding_note='Source method claim 0 supports the unchanged model label.')
    assert certificate['grounded_result']['methods'] == ['Model']
    assert analysis.result['field_evidence'] == {'summary': [0]}


@pytest.mark.parametrize('large_evidence', [False, True])
def test_api_attaches_versioned_review_without_duplicate_or_historical_rewrite(large_evidence):
    analysis, raw, peer, coordinator, pdf = fixture()
    if large_evidence:
        raw += ' ' * 220000
        peer['result_sha256'] = coordinator['result_sha256'] = text_hash(raw)
    folder = DATA / 'documents'; folder.mkdir(exist_ok=True)
    (folder / (hashlib.sha256(b'p1').hexdigest() + 'v1.pdf')).write_bytes(pdf)
    (folder / (analysis.content_hash + '.json')).write_text(json.dumps(PAGES), 'utf8')
    original = copy.deepcopy(analysis.result)
    with Session.begin() as s:
        s.add(Paper(id='p1', title='Fixture', abstract='Fixture', published=now(), updated=now()))
        row = Analysis(paper_id='p1', domain_id='molecules', version=1, taxonomy_version=1,
                       model='gpt-6.1-sol', content_hash=analysis.content_hash, result=original)
        s.add(row); s.flush(); aid = row.id
    client = TestClient(app); headers = {'X-Atlas-Client': '1'}
    work = client.post('/api/collaboration', headers=headers, json={'title': 'Attach reviewed evidence',
        'instruction': 'Bind exact independent review to original analysis.', 'paper_ids': ['p1'], 'kind': 'curation'}).json()
    lease = client.post('/api/collaboration/' + work['id'] + '/claim', headers=headers, json={'owner': 'fixture-coordinator'}).json()
    body = {'token': lease['lease_token'], 'revision': lease['revision'], 'analysis_id': aid,
            'generation_agent': '/author', 'raw_result': raw, 'raw_report': REPORT, 'independent': peer, 'coordinator': coordinator}
    route = '/api/collaboration/' + work['id'] + '/publish-analysis-review'
    changed = copy.deepcopy(body); changed['independent']['report_sha256'] = 'f' * 64
    assert client.post(route, headers=headers, json=changed).status_code == 422
    response = client.post(route, headers=headers, json=body)
    assert response.status_code == 200, response.text
    detail = client.get('/api/paper?id=p1').json()['analysis']
    listed = client.get('/api/papers?days=0').json()['items'][0]['analysis']
    assert detail['id'] == aid and detail['result']['fulltext_markdown'] == REPORT
    assert detail['quality']['semantic'] == listed['quality']['semantic'] == 'model_reviewed'
    assert detail['quality']['evidence'] == 'verified'
    with Session() as s:
        assert s.get(Analysis, aid).result == original
        assert s.get(Setting, 'analysis-independent-review:' + str(aid)) is not None
    assert client.post(route, headers=headers, json=body).status_code == 409


def test_only_line_endings_and_outer_whitespace_may_differ_from_reviewed_report():
    analysis, raw, peer, coordinator, _ = fixture()
    approved_report = '\r\n' + REPORT.replace('\n', '\r\n') + '\r\n'
    peer['report_sha256'] = coordinator['report_sha256'] = text_hash(approved_report)
    args = (analysis, PAGES, raw, '/author', ReviewReceipt(**peer), ReviewReceipt(**coordinator))
    certificate = make_certificate(*args, raw_report=approved_report)
    assert certificate['report_sha256'] != certificate['stored_report_sha256']
    with pytest.raises(ValueError, match='报告正文'):
        make_certificate(*args, raw_report=approved_report.replace('source interpretation', 'unsupported amendment'))

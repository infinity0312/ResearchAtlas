"""Local commercial pilot: real source-bound evidence, no model/network calls."""
import copy
import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app import app
from backend.db import Analysis, Base, DATA, Paper, Session, Setting, engine, now
from backend.contracts import Extraction
from backend.independent_review import FACETS, ReviewReceipt, make_certificate, text_hash

C = TestClient(app)
H = {'X-Atlas-Client': '1'}
ROOT = '/api/projects'


@pytest.fixture(autouse=True)
def no_paid_calls(monkeypatch):
    from backend.analysis import DeepSeek
    monkeypatch.setattr(DeepSeek, 'generate', lambda *a, **k: pytest.fail('Product workflow must not call models'))


def post(path='', data=None):
    return C.post(ROOT + path, json=data or {}, headers=H)


def detail(project):
    return C.get(ROOT + '/' + project['id']).json()


def create():
    response = post(data={'title': '材料路线决策', 'scenario': 'route_review', 'owner': '研发负责人',
        'question': '是否采用候选图网络路线？', 'constraints': '仅考虑分子数据',
        'criteria': [{'id': 'performance', 'label': '性能与适用性'}]})
    assert response.status_code in (200, 201), response.text
    return response.json()


def edit(project, **changes):
    current = detail(project)['project']
    body = {k: current[k] for k in ('revision', 'title', 'owner', 'question', 'constraints',
        'criteria', 'recommendation', 'open_questions')}
    return C.put(ROOT + '/' + project['id'], headers=H, json={**body, **changes})


def seed(reviewed=True):
    quote = 'We propose a verified molecular model.'
    pages = [{'page': 1, 'text': quote}]
    report = '# Source review\n\n' + 'Detailed source interpretation. ' * 50
    raw = json.dumps({'summary': 'Verified', 'methods': ['Model'], 'topics': [], 'problems': [],
        'claims': [{'kind': 'method', 'text': 'Method', 'page': 1, 'quote': quote}],
        'field_evidence': {'summary': [0], 'methods.0': [0]}})
    pdf = b'%PDF-product-test-only'
    digest = hashlib.sha256(pdf).hexdigest()
    folder = DATA / 'documents'; folder.mkdir(exist_ok=True)
    (folder / (hashlib.sha256(b'product-paper').hexdigest() + 'v1.pdf')).write_bytes(pdf)
    (folder / (digest + '.json')).write_text(json.dumps(pages), encoding='utf8')
    with Session.begin() as s:
        s.add(Paper(id='product-paper', title='Reviewed model', abstract='source', published=now(), updated=now()))
        row = Analysis(paper_id='product-paper', domain_id='molecules', version=1, taxonomy_version=1,
            model='fixture', content_hash=digest, result={**Extraction.model_validate_json(raw).model_dump(),
                'fulltext_markdown': report, 'provenance': {'generation_model': 'gpt-6.1-sol'}})
        s.add(row); s.flush()
        if reviewed:
            receipt = dict(decision='approved', blocking_issues=[], reviewer_model='gpt-6.1-sol',
                reviewer_agent='/peer', report_sha256=text_hash(report), result_sha256=text_hash(raw),
                content_hash=digest, reviewed_pages=[1], checks={k: {'status': 'passed', 'note': 'Source-bound review.'} for k in FACETS})
            certificate = make_certificate(row, pages, raw, '/author', ReviewReceipt(**receipt),
                ReviewReceipt(**{**receipt, 'reviewer_agent': '/coordinator', 'reviewer_model': 'codex'}))
            s.add(Setting(key='analysis-independent-review:' + str(row.id), value=certificate))
        return row.id


def attach(project, aid, **changes):
    return post('/' + project['id'] + '/evidence', {'revision': detail(project)['project']['revision'],
        'analysis_id': aid, 'claim_index': 0, 'criterion_id': 'performance', 'stance': 'supports',
        'context': '适用于当前分子任务工况', **changes})


def review(project):
    return post('/' + project['id'] + '/review', {'revision': detail(project)['project']['revision'],
        'reviewer': '独立评审', 'note': '已检查来源适用性与决策限制。'})


def ready_project():
    project = create(); aid = seed()
    assert edit(project, recommendation='采用候选路线进行受控试验').status_code == 200
    assert attach(project, aid).status_code in (200, 201)
    assert review(project).status_code in (200, 201)
    return project, aid


def database_snapshot():
    with engine.connect() as conn:
        return {table.name: [tuple(row) for row in conn.execute(table.select())]
                for table in Base.metadata.sorted_tables}


def test_catalog_and_reads_do_not_write_or_call_models(monkeypatch):
    from backend.analysis import DeepSeek
    monkeypatch.setattr(DeepSeek, 'generate', lambda *a, **k: pytest.fail('Product reads must not call models'))
    project = create(); before = database_snapshot()
    catalog = C.get(ROOT + '/catalog').json()
    assert catalog['deployment'] == {'mode': 'local', 'authenticated_identity': False,
        'tenant_isolation': False, 'fulltext_export': False}
    assert {s['id'] for s in catalog['scenarios']} == {'route_review', 'material_substitution', 'change_review'}
    for path in ('', '/library', '/' + project['id']):
        assert C.get(ROOT + path).status_code == 200
    assert database_snapshot() == before


@pytest.mark.parametrize('reviewed', [False, True])
def test_unreviewed_and_invalid_claim_never_pass_gate(reviewed):
    project = create(); aid = seed(reviewed)
    assert edit(project, recommendation='采用候选路线进行受控试验').status_code == 200
    assert attach(project, aid, claim_index=999).status_code == 422
    assert attach(project, aid, claim_index=-1).status_code == 422
    assert not detail(project)['evidence']
    assert review(project).status_code == 422
    result = attach(project, aid)
    if not reviewed:
        assert result.status_code == 422 or not detail(project)['readiness']['can_review']
        assert review(project).status_code == 422
    else:
        assert result.status_code in (200, 201)
        assert detail(project)['readiness']['can_review']


def test_revision_conflict_and_cross_project_evidence_are_rejected():
    project = create(); other = create(); aid = seed()
    evidence = attach(project, aid)
    assert evidence.status_code in (200, 201), evidence.text
    assert edit(project, revision=1, recommendation='旧客户端覆盖').status_code == 409
    eid = evidence.json()['id']
    result = C.delete(ROOT + '/' + other['id'] + '/evidence/' + eid + '?revision=1', headers=H)
    assert result.status_code in (404, 409)
    assert len(detail(project)['evidence']) == 1
    assert edit(project, criteria=[]).status_code in (409, 422)


def test_source_change_invalidates_approved_project():
    project, aid = ready_project()
    assert detail(project)['readiness']['can_deliver']
    with Session.begin() as s:
        s.get(Paper, 'product-paper').version = 2
    assert not detail(project)['readiness']['can_deliver']
    assert post('/' + project['id'] + '/deliveries', {'revision': detail(project)['project']['revision']}).status_code == 422


def test_tampered_reviewed_analysis_cannot_reuse_approval():
    project, aid = ready_project()
    with Session.begin() as s:
        row = s.get(Analysis, aid)
        row.result = {**row.result, 'summary': 'Unreviewed amendment'}
    assert not detail(project)['readiness']['can_deliver']
    assert review(project).status_code == 422


def test_corrected_source_and_new_analysis_cannot_reuse_frozen_evidence():
    project, aid = ready_project()
    with Session.begin() as s:
        row = s.get(Analysis, aid)
        old_hash = row.content_hash
        s.add(Setting(key='source-edit:' + old_hash, value={'paper_id': 'product-paper',
            'paper_version': 1, 'digest': 'f' * 64, 'previous': old_hash, 'updated': now()}))
    assert not detail(project)['readiness']['can_review']
    assert review(project).status_code == 422


def test_contradiction_is_preserved_in_delivery_and_open_questions_are_allowed():
    project = create(); aid = seed()
    assert edit(project, recommendation='暂不采用该路线，先执行受控验证', open_questions='尚需补充外部数据验证').status_code == 200
    assert attach(project, aid, stance='contradicts').status_code in (200, 201)
    assert detail(project)['readiness']['contradiction_count'] == 1
    assert review(project).status_code in (200, 201)
    response = post('/' + project['id'] + '/deliveries', {'revision': detail(project)['project']['revision']})
    assert response.status_code in (200, 201), response.text
    assert response.json()['manifest']['evidence'][0]['stance'] == 'contradicts'
    assert response.json()['manifest']['project']['open_questions'] == '尚需补充外部数据验证'


def test_edit_invalidates_review_and_delivery_is_immutable_idempotent():
    project, aid = ready_project()
    revision = detail(project)['project']['revision']
    route = '/' + project['id'] + '/deliveries'
    response = post(route, {'revision': revision})
    assert response.status_code in (200, 201), response.text
    delivery = response.json(); frozen = copy.deepcopy(delivery)
    repeated = post(route, {'revision': detail(project)['project']['revision']})
    assert repeated.status_code in (200, 201), repeated.text
    assert repeated.json()['id'] == delivery['id']
    assert len(detail(project)['deliveries']) == 1
    before = database_snapshot()
    for kind in ('md', 'json'):
        exported = C.get(ROOT + route + '/' + delivery['id'] + '/export?format=' + kind)
        assert exported.status_code == 200
        assert b'%PDF-product-test-only' not in exported.content
        assert b'Detailed source interpretation.' not in exported.content
    assert database_snapshot() == before
    assert edit(project, recommendation='调整为验证后再采用').status_code == 200
    assert not detail(project)['readiness']['can_deliver']
    assert C.get(ROOT + route + '/' + delivery['id']).json() == frozen
    other = create()
    assert C.get(ROOT + '/' + other['id'] + '/deliveries/' + delivery['id']).status_code == 404


def test_uncertain_evidence_blocks_review_and_delivery():
    project = create(); aid = seed()
    assert edit(project, recommendation='有条件采用').status_code == 200
    assert attach(project, aid, stance='uncertain').status_code in (200, 201)
    assert not detail(project)['readiness']['can_deliver']
    assert post('/' + project['id'] + '/deliveries', {'revision': detail(project)['project']['revision']}).status_code == 422


def test_blank_applicability_and_padded_review_are_not_substantive():
    project = create(); aid = seed()
    assert attach(project, aid, context='    ').status_code == 422
    assert edit(project, recommendation='采用候选路线进行受控试验').status_code == 200
    assert attach(project, aid).status_code in (200, 201)
    response = post('/' + project['id'] + '/review', {'revision': detail(project)['project']['revision'],
        'reviewer': '评审人员', 'note': '       好'})
    assert response.status_code == 422


def plan(project, **changes):
    return post('/' + project['id'] + '/validations', {'revision': detail(project)['project']['revision'],
        'criterion_id': 'performance', 'title': '受控分子验证', 'success_criteria': '在独立测试集达到预定性能阈值',
        'owner': '实验负责人', **changes})


def feedback(project, validation, **changes):
    return C.put(ROOT + '/' + project['id'] + '/validations/' + validation['id'], headers=H,
        json={'revision': detail(project)['project']['revision'], 'status': 'completed',
            'outcome': 'contradicts', 'observation': '独立测试集性能低于预定阈值，需要调整方案。', **changes})


def test_validation_cannot_be_falsely_completed_or_cross_project_changed():
    project = create(); other = create()
    assert plan(project, criterion_id='unknown').status_code == 422
    response = plan(project)
    assert response.status_code in (200, 201), response.text
    validation = response.json()
    assert (validation['status'], validation['outcome']) == ('planned', 'pending')
    before = database_snapshot()
    for fields in ({'outcome': 'pending'}, {'observation': '太短'},
                   {'observation': '          好'}, {'status': 'planned', 'outcome': 'supports'}):
        assert feedback(project, validation, **fields).status_code == 422
    assert feedback(other, validation).status_code == 404
    assert database_snapshot() == before
    assert edit(project, criteria=[{'id': 'new', 'label': '新的标准'}]).status_code == 422
    assert feedback(project, validation, revision=1).status_code == 409
    assert detail(project)['validations'][0]['status'] == 'planned'


def test_validation_feedback_invalidates_review_but_preserves_delivered_plan():
    project, aid = ready_project()
    response = plan(project)
    assert response.status_code in (200, 201), response.text
    validation = response.json()
    assert not detail(project)['readiness']['can_deliver']
    assert review(project).status_code in (200, 201)
    route = '/' + project['id'] + '/deliveries'
    response = post(route, {'revision': detail(project)['project']['revision']})
    assert response.status_code in (200, 201), response.text
    frozen = response.json()
    assert frozen['manifest']['validations'][0]['status'] == 'planned'
    assert feedback(project, validation).status_code == 200
    current = detail(project)
    assert current['validations'][0]['outcome'] == 'contradicts'
    assert not current['readiness']['can_deliver']
    assert post(route, {'revision': current['project']['revision']}).status_code == 422
    assert C.get(ROOT + route + '/' + frozen['id']).json() == frozen
    assert review(project).status_code in (200, 201)
    second = post(route, {'revision': detail(project)['project']['revision']})
    assert second.status_code in (200, 201), second.text
    assert second.json()['id'] != frozen['id']
    assert second.json()['manifest']['validations'][0]['outcome'] == 'contradicts'
    assert '未独立' in second.json()['markdown']

"""Actionable project recovery; reuse real independent-review evidence fixtures."""
import copy

import pytest
from test_product_projects import C, H, ROOT, attach, create, detail, edit, plan, post, ready_project, review, seed
from backend.db import Analysis, Session, Setting


@pytest.fixture(autouse=True)
def no_paid_calls(monkeypatch):
    from backend.analysis import DeepSeek
    monkeypatch.setattr(DeepSeek, 'generate', lambda *a, **k: pytest.fail('Recovery must not call models'))


def replace(project, evidence, **changes):
    body = dict(revision=detail(project)['project']['revision'], analysis_id=evidence['analysis_id'],
        claim_index=evidence['snapshot']['claim_index'], criterion_id=evidence['criterion_id'],
        stance=evidence['stance'], context=evidence['context'])
    return C.put(ROOT + '/' + project['id'] + '/evidence/' + evidence['id'], headers=H,
                 json={**body, **changes})


def state(project):
    d = detail(project)
    listed = next(p for p in C.get(ROOT).json()['items'] if p['id'] == project['id'])
    for field in ('next_action', 'next_action_label', 'pending_validations', 'review_valid', 'review_outdated'):
        assert listed['readiness'][field] == d['readiness'][field]
    assert d['readiness']['next_action_label']
    return d['readiness']


def test_next_actions_follow_real_gates_and_preserve_review_semantics():
    project = create()
    assert state(project)['next_action'] == 'complete_decision'
    assert edit(project, recommendation='采用候选路线进行受控试验').status_code == 200
    assert state(project)['next_action'] == 'collect_evidence'
    aid = seed()
    assert attach(project, aid).status_code == 200
    assert state(project)['next_action'] == 'review_decision'
    assert not state(project)['review_valid']
    assert review(project).status_code == 200
    assert state(project)['next_action'] == 'freeze_delivery'
    assert state(project)['review_valid']
    assert post('/' + project['id'] + '/deliveries', {'revision': detail(project)['project']['revision']}).status_code == 200
    assert state(project)['next_action'] == 'monitor_sources'
    assert plan(project).status_code == 200
    assert state(project)['pending_validations'] == 1
    assert state(project)['review_outdated']
    assert state(project)['next_action'] == 'review_decision'
    assert review(project).status_code == 200
    assert state(project)['next_action'] == 'freeze_delivery'
    assert post('/' + project['id'] + '/deliveries', {'revision': detail(project)['project']['revision']}).status_code == 200
    assert state(project)['next_action'] == 'run_validation'


def test_replacement_is_server_bound_audited_and_old_delivery_immutable():
    project, aid = ready_project()
    frozen = post('/' + project['id'] + '/deliveries', {'revision': detail(project)['project']['revision']}).json()
    original = detail(project)['evidence'][0]
    response = replace(project, original, stance='contradicts', context='在本项目工况中仅作为边界反例',
                       quote='Client invented quotation', snapshot={'quote': 'Fabricated'})
    assert response.status_code == 200, response.text
    current = detail(project)
    assert len(current['evidence']) == 1
    replacement = current['evidence'][0]
    assert replacement['id'] != original['id']
    assert replacement['snapshot']['quote'] == original['snapshot']['quote']
    assert replacement['stance'] == 'contradicts'
    assert not current['readiness']['can_deliver']
    assert current['readiness']['review_outdated']
    events = [e for e in current['events'] if e['action'] == 'evidence_replaced']
    assert len(events) == 1
    assert 'before' in events[0]['detail'] and 'after' in events[0]['detail']
    assert C.get(ROOT + '/' + project['id'] + '/deliveries/' + frozen['id']).json() == frozen
    assert review(project).status_code == 200


def test_replacement_noop_stale_revision_ownership_and_invalid_inputs_are_atomic():
    project, aid = ready_project(); original = detail(project)['evidence'][0]
    before = detail(project)
    response = replace(project, original)
    assert response.status_code == 200
    assert response.json()['id'] == original['id']
    assert detail(project) == before
    assert replace(project, original, revision=1, context='旧版本覆盖请求').status_code == 409
    other = create()
    assert replace(other, original).status_code == 404
    for changes in ({'claim_index': 999}, {'criterion_id': 'unknown'}, {'analysis_id': 999999}):
        assert replace(project, original, **changes).status_code in (404, 409, 422)
        assert detail(project) == before
    assert edit(project, criteria=[*before['project']['criteria'], {'id': 'risk', 'label': '失败风险'}]).status_code == 200
    assert attach(project, aid, criterion_id='risk').status_code == 200
    before_duplicate = detail(project)
    assert replace(project, original, criterion_id='risk').status_code in (409, 422)
    assert detail(project) == before_duplicate


def test_source_repair_precedes_other_actions_and_requires_fresh_project_review():
    project, aid = ready_project(); original = detail(project)['evidence'][0]
    # Replacing the independent receipt revokes eligibility without product writes.
    with Session.begin() as s:
        old = s.get(Setting, 'analysis-independent-review:' + str(aid))
        certificate = copy.deepcopy(old.value)
        s.delete(old)
    assert state(project)['next_action'] == 'repair_evidence'
    assert not state(project)['review_valid']
    assert edit(project, owner='').status_code == 200
    assert state(project)['next_action'] == 'repair_evidence'
    assert edit(project, owner='研发负责人').status_code == 200
    # A genuinely reviewed newer analysis is published, not arbitrary quality flags.
    with Session.begin() as s:
        old = s.get(Analysis, aid)
        newer = Analysis(paper_id=old.paper_id, domain_id=old.domain_id, version=old.version,
            taxonomy_version=old.taxonomy_version, model=old.model, content_hash=old.content_hash,
            result=copy.deepcopy(old.result))
        s.add(newer); s.flush()
        certificate['analysis_id'] = newer.id
        s.add(Setting(key='analysis-independent-review:' + str(newer.id), value=certificate))
        new_id = newer.id
    response = replace(project, original, analysis_id=new_id)
    assert response.status_code == 200, response.text
    assert state(project)['next_action'] == 'review_decision'
    assert detail(project)['readiness']['can_review']
    assert not detail(project)['readiness']['can_deliver']
    assert review(project).status_code == 200
    assert state(project)['next_action'] == 'freeze_delivery'

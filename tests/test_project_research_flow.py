"""Candidate discovery stays outside the reviewed decision aggregate."""
import copy
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import MetaData, create_engine, inspect, select

from test_product_projects import C, H, ROOT, attach, create, database_snapshot, detail, post, ready_project, seed
from backend.db import Analysis, Base, Paper, Session, Setting
from backend.migrations import MIGRATIONS, MigrationError, run_migrations
from backend.product.models import ProductEvent, ProjectCandidate, ProjectEvidence


@pytest.fixture(autouse=True)
def no_model(monkeypatch):
    from backend.analysis import DeepSeek
    monkeypatch.setattr(DeepSeek, 'generate', lambda *a, **k: pytest.fail('Research flow must not call models'))


def candidate(project, **changes):
    return post('/' + project['id'] + '/candidates', {'paper_id': 'product-paper', 'reason': '候选发现的适用性说明', **changes})


def update(project, cid, **changes):
    body = {'revision': 1, 'status': 'kept', 'reason': '符合当前研究工况', **changes}
    return C.put(ROOT + '/' + project['id'] + '/candidates/' + cid, json=body, headers=H)


def test_candidate_idempotence_revision_snapshot_and_review_are_independent():
    project, aid = ready_project()
    delivery = post('/' + project['id'] + '/deliveries', {'revision': detail(project)['project']['revision']}).json()
    before = detail(project)
    response = candidate(project)
    assert response.status_code == 200, response.text
    item = response.json()
    assert item['status'] == 'pending' and item['revision'] == 1
    assert item['title'] == 'Reviewed model' and item['paper_version'] == 1
    assert item['analysis_available'] and item['binding_count'] == 1
    repeated = candidate(project, reason='重复请求不应覆盖原始理由').json()
    assert repeated == item
    changed = update(project, item['id']).json()
    assert changed['revision'] == 2 and changed['status'] == 'kept'
    assert update(project, item['id']).status_code == 409
    no_op = update(project, item['id'], revision=2)
    assert no_op.json() == changed
    after = detail(project)
    for field in ('project', 'evidence', 'reviews', 'deliveries', 'readiness'):
        assert after[field] == before[field]
    assert C.get(ROOT + '/' + project['id'] + '/deliveries/' + delivery['id']).json() == delivery
    events = [e for e in after['events'] if e['action'].startswith('candidate_')]
    assert len(events) == 2
    event = next(e for e in events if e['action'] == 'candidate_updated')
    assert event['detail']['before']['status'] == 'pending'
    assert event['detail']['after']['status'] == 'kept'
    with Session.begin() as s:
        paper = s.get(Paper, 'product-paper'); paper.version = 2; paper.title = 'Current changed title'
    fresh = C.get(ROOT + '/' + project['id'] + '/candidates').json()
    assert fresh['total'] == 1
    assert fresh['items'][0]['title'] == item['title']
    assert fresh['items'][0]['paper_version'] == 1 and fresh['items'][0]['current_version'] == 2


def test_candidate_writes_have_strict_boundaries_and_project_ownership():
    project = create(); other = create(); seed()
    item = candidate(project).json()
    assert update(other, item['id']).status_code == 404
    for change in ({'reason': '   好'}, {'reason': 'x' * 5001}, {'status': 'unknown'},
                   {'revision': True}, {'revision': '1'}, {'paper_id': 'injected'}):
        assert update(project, item['id'], **change).status_code == 422
    assert C.get(ROOT + '/' + project['id'] + '/candidates').json()['items'][0] == item
    pending = update(project, item['id'], status='pending', reason='')
    assert pending.status_code == 200
    assert candidate(project, paper_id='missing').status_code == 404
    assert candidate(project, paper_id='   ').status_code == 422
    assert post('/missing-project/candidates', {'paper_id': 'product-paper'}).status_code == 404
    assert C.get(ROOT + '/missing-project/candidates').status_code == 404
    assert C.get(ROOT + '/' + project['id'] + '/candidates').json()['items'][0] == pending.json()


def test_duplicate_candidate_posts_serialize_without_duplicate_rows():
    project = create(); seed()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: candidate(project), range(2)))
    assert [r.status_code for r in results] == [200, 200]
    assert results[0].json()['id'] == results[1].json()['id']
    with Session() as s:
        assert len(list(s.scalars(select(ProjectCandidate)))) == 1
        assert len(list(s.scalars(select(ProductEvent).where(ProductEvent.action == 'candidate_added')))) == 1


def test_reverse_links_include_candidate_and_evidence_without_inventing_projects():
    bound, aid = ready_project(); shortlisted = create(); unrelated = create()
    item = candidate(shortlisted).json()
    links = C.get(ROOT + '/paper-links?paper_id=product-paper')
    assert links.status_code == 200, links.text
    by_id = {p['project_id']: p for p in links.json()['items']}
    assert set(by_id) == {bound['id'], shortlisted['id']}
    assert by_id[shortlisted['id']]['candidate']['id'] == item['id']
    assert by_id[shortlisted['id']]['evidence'] == []
    assert by_id[bound['id']]['candidate'] is None
    assert by_id[bound['id']]['evidence'][0]['eligible']
    assert by_id[bound['id']]['evidence'][0]['criterion_label'] == '性能与适用性'
    assert C.get(ROOT + '/paper-links?paper_id=missing').json() == {'items': []}


def test_impacts_use_live_quality_and_ids_without_touching_decision_history():
    project, aid = ready_project(); other = create(); assert attach(other, aid).status_code == 200
    assert C.get(ROOT + '/impacts').json() == {'items': [], 'total': 0}
    before = copy.deepcopy(detail(project))
    with Session.begin() as s:
        receipt = s.get(Setting, 'analysis-independent-review:' + str(aid))
        s.delete(receipt)
    impacts = C.get(ROOT + '/impacts').json()
    assert impacts['total'] == 2
    assert {item['kind'] for item in impacts['items']} == {'needs_verification'}
    assert all(item['bound_analysis_id'] == item['latest_analysis_id'] == aid for item in impacts['items'])
    with Session.begin() as s:
        s.get(Paper, 'product-paper').version = 2
    changed = C.get(ROOT + '/impacts').json()
    assert {item['kind'] for item in changed['items']} == {'source_changed'}
    assert all(item['bound_paper_version'] == 1 and item['current_paper_version'] == 2 for item in changed['items'])
    assert detail(project)['project'] == before['project']
    assert detail(project)['events'] == before['events']


def test_flow_reads_are_pure_and_candidate_missing_paper_retains_discovery_snapshot():
    project = create(); seed(); item = candidate(project).json()
    before = database_snapshot()
    for path in ('/impacts', '/paper-links?paper_id=product-paper', '/' + project['id'] + '/candidates'):
        assert C.get(ROOT + path).status_code == 200
    assert database_snapshot() == before
    with Session.begin() as s:
        s.delete(s.get(Paper, 'product-paper'))
    missing = C.get(ROOT + '/' + project['id'] + '/candidates').json()['items'][0]
    assert missing['current_version'] is None
    assert (missing['title'], missing['paper_version']) == (item['title'], 1)
    # The idempotency key still resolves after the live paper disappears.
    assert candidate(project).json()['id'] == item['id']


def test_candidate_migration_upgrades_v5_and_missing_table_fails_closed(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'flow.db'))
    try:
        legacy = MetaData()
        for table in Base.metadata.sorted_tables:
            if table.name not in ('project_candidates', 'project_trend_leads', 'project_paper_intakes'): table.to_metadata(legacy)
        assert run_migrations(engine, legacy, MIGRATIONS[:5]) == [1, 2, 3, 4, 5]
        with engine.begin() as connection:
            connection.exec_driver_sql("INSERT INTO settings(key,value) VALUES ('flow-preserved','{}')")
        assert run_migrations(engine, Base.metadata) == [6, 7, 8, 9]
        assert run_migrations(engine, Base.metadata) == []
        assert inspect(engine).has_table('project_candidates')
        with engine.begin() as connection:
            assert connection.exec_driver_sql("SELECT value FROM settings WHERE key='flow-preserved'").scalar() == '{}'
            connection.exec_driver_sql('DROP TABLE project_candidates')
        with pytest.raises(MigrationError, match='project_candidates'):
            run_migrations(engine, Base.metadata)
        assert not inspect(engine).has_table('project_candidates')
    finally:
        engine.dispose()


@pytest.mark.parametrize('corruption', ['snapshot-null', 'snapshot-missing', 'quote-missing', 'snapshot-version', 'claims-null',
                                      'claims-empty', 'claim-invalid', 'result-list', 'negative-index'])
def test_impacts_and_reverse_links_fail_closed_on_incomplete_bound_records(corruption):
    project, aid = ready_project()
    with Session.begin() as s:
        evidence = s.scalar(select(ProjectEvidence).where(ProjectEvidence.project_id == project['id']))
        analysis = s.get(Analysis, aid)
        if corruption == 'snapshot-null': evidence.snapshot = None
        elif corruption == 'snapshot-missing': evidence.snapshot = {'paper_title': 'Incomplete snapshot'}
        elif corruption == 'quote-missing': evidence.snapshot = {k: v for k, v in evidence.snapshot.items() if k != 'quote'}
        elif corruption == 'snapshot-version': evidence.snapshot = {**evidence.snapshot, 'paper_version': 77}
        elif corruption == 'claims-null': analysis.result = {**analysis.result, 'claims': None}
        elif corruption == 'claims-empty': analysis.result = {**analysis.result, 'claims': []}
        elif corruption == 'claim-invalid': analysis.result = {**analysis.result, 'claims': [None]}
        elif corruption == 'result-list': analysis.result = []
        elif corruption == 'negative-index': evidence.claim_index = -1
    before = database_snapshot()
    impact = C.get(ROOT + '/impacts')
    assert impact.status_code == 200, impact.text
    assert impact.json()['total'] == 1
    assert impact.json()['items'][0]['kind'] == 'source_changed'
    assert impact.json()['items'][0]['issues']
    links = C.get(ROOT + '/paper-links?paper_id=product-paper')
    assert links.status_code == 200, links.text
    assert not links.json()['items'][0]['evidence'][0]['eligible']
    assert database_snapshot() == before

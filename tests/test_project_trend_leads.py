import copy
from urllib.parse import urlencode

import pytest
from sqlalchemy import MetaData, create_engine, inspect, select

from test_product_projects import C, H, ROOT, create, database_snapshot, detail, post, ready_project
from backend.db import Base, Paper, Session, Setting, TrendCount, TrendEvidence, TrendSeries
from backend.migrations import MIGRATIONS, MigrationError, run_migrations
from backend.product.models import ProjectCandidate, ProjectTrendLead
from backend.trends import buckets, key
from backend.trend_signals import period_key


@pytest.fixture(autouse=True)
def stored_data_only(monkeypatch):
    from backend.analysis import DeepSeek
    from backend import trends, trend_signals
    def fail(*args, **kwargs): pytest.fail('Trend leads may not use models, network or background jobs')
    monkeypatch.setattr(DeepSeek, 'generate', fail)
    monkeypatch.setattr(trends, 'count_remote', fail)
    monkeypatch.setattr(trends, 'enqueue', fail)
    monkeypatch.setattr(trend_signals, 'collect', fail)


def stored_trend():
    with Session.begin() as s:
        s.add(TrendSeries(id='lead-series', name='Stored direction', query='ti:"lead fixture"', color='#327c72'))
        s.add(Setting(key='trend_series_aliases', value={'old-lead-id': 'lead-series'}))
        for index, (label, lo, hi) in enumerate(buckets('2022', '2024', 'year')):
            s.add(TrendCount(key=key('ti:"lead fixture"', lo, hi), count=100+index*10,
                             source='arxiv-official-search', fetched='2025-01-01T00:00:00+00:00'))
        papers = [{'id': pid, 'title': title, 'quote': 'Exact stored source quotation.',
            'bottleneck': 'Concrete unresolved bottleneck', 'relevant': relevant,
            'exclusion_reason': '' if relevant else 'Not in selected scope',
            'novelty': 75, 'rigor': 70, 'headroom': 60, 'family': 'Graph network',
            'headroom_quote': 'Explicit unresolved boundary.',
            'headroom_source': {'url': 'https://example.invalid/source', 'section': 'Limitations'}}
            for pid, title, relevant in [('product-paper', 'Stored sample title', True),
                ('second-local', 'Second local', True), ('external-only', 'External sample', True),
                ('excluded-local', 'Out-of-scope local', False)]]
        for pid in ('second-local', 'excluded-local'):
            s.add(Paper(id=pid, title='Local '+pid, abstract='fixture', published='2024-01-01', updated='2024-01-01'))
        _, lo, hi = buckets('2024', '2024', 'year')[0]
        s.add(TrendEvidence(key=period_key('ti:"lead fixture"', lo, hi, 'codex-source-review'),
            result={'population': 120, 'papers': papers, 'sample': len(papers)}))


def preview(**changes):
    query = {'series_id': 'lead-series', 'start': '2022', 'end': '2024', 'interval': 'year', **changes}
    return C.get(ROOT+'/trend-preview?'+urlencode(query))


def capture(project, source, **changes):
    return post('/'+project['id']+'/trend-leads', {'series_id': 'lead-series', 'start': '2022',
        'end': '2024', 'interval': 'year', 'source_key': source['source_key'],
        'reason': '值得继续核对的真实研究方向', 'paper_ids': [], **changes})


def test_preview_matches_stored_trends_aliases_and_is_pure():
    project, aid = ready_project(); stored_trend()
    before = database_snapshot()
    source = preview().json()
    assert preview(series_id='old-lead-id').json() == source
    direction = C.get('/api/trends/data?ids=lead-series&start=2022&end=2024&interval=year').json()['series'][0]
    snap = source['snapshot']
    assert snap['points'] == direction['points']
    assert snap['growth'] == direction['growth']
    assert (snap['signal']['x'], snap['signal']['y']) == (direction['insight']['x'], direction['insight']['y'])
    assert snap['scope']['period'] == '2024'
    assert len(snap['papers']) == 4 and snap['papers'][0]['local_version'] == 1
    assert snap['papers'][2]['local_version'] is None
    assert database_snapshot() == before


def test_capture_candidates_is_atomic_idempotent_and_outside_reviewed_decision():
    project, aid = ready_project(); stored_trend()
    frozen = post('/'+project['id']+'/deliveries', {'revision': detail(project)['project']['revision']}).json()
    before = detail(project)
    source = preview().json()
    result = capture(project, source, paper_ids=['product-paper', 'product-paper'])
    assert result.status_code == 200, result.text
    lead = result.json()
    assert len(lead['candidate_ids']) == 1 and lead['snapshot'] == source['snapshot']
    assert not lead['source_changed'] and lead['current_source_available']
    duplicate = capture(project, source, paper_ids=['second-local'], reason='重复请求应保留最初判断')
    assert duplicate.json() == lead
    with Session() as s:
        assert len(list(s.scalars(select(ProjectCandidate)))) == 1
        assert len(list(s.scalars(select(ProjectTrendLead)))) == 1
    after = detail(project)
    for field in ('project', 'readiness', 'evidence', 'reviews', 'deliveries'):
        assert after[field] == before[field]
    assert C.get(ROOT+'/'+project['id']+'/deliveries/'+frozen['id']).json() == frozen


def test_lead_reuses_existing_candidate_without_overwriting_discovery_reason():
    project, aid = ready_project(); stored_trend()
    existing = post('/'+project['id']+'/candidates', {'paper_id': 'product-paper', 'reason': '先前独立发现的理由'}).json()
    lead = capture(project, preview().json(), paper_ids=['product-paper']).json()
    assert lead['candidate_ids'] == [{'paper_id': 'product-paper', 'candidate_id': existing['id']}]
    candidates = C.get(ROOT+'/'+project['id']+'/candidates').json()
    assert candidates['total'] == 1 and candidates['items'][0] == existing


@pytest.mark.parametrize('papers', [['external-only'], ['excluded-local'], ['not-in-sample'], ['product-paper', 'external-only']])
def test_external_out_of_scope_and_unknown_papers_cannot_become_candidates(papers):
    project, aid = ready_project(); stored_trend(); source = preview().json()
    before = database_snapshot()
    response = capture(project, source, paper_ids=papers)
    assert response.status_code == 422, response.text
    assert database_snapshot() == before
    assert capture(project, source).status_code == 200  # Direction itself is honest provenance.


def test_source_drift_rejects_capture_and_does_not_rewrite_frozen_history():
    project, aid = ready_project(); stored_trend(); source = preview().json()
    lead = capture(project, source).json(); original = copy.deepcopy(lead['snapshot'])
    with Session.begin() as s:
        _, lo, hi = buckets('2024', '2024', 'year')[0]
        s.get(TrendCount, key('ti:"lead fixture"', lo, hi)).count = 200
    before = database_snapshot()
    assert capture(project, source).status_code == 409
    assert database_snapshot() == before
    listed = C.get(ROOT+'/'+project['id']+'/trend-leads').json()['items'][0]
    assert listed['snapshot'] == original and listed['source_changed'] and listed['current_source_available']
    new_source = preview().json()
    assert new_source['source_key'] != source['source_key']
    assert capture(project, new_source).json()['id'] != lead['id']


def test_lead_revision_ownership_noop_and_immutable_snapshot():
    project, aid = ready_project(); other = create(); stored_trend(); source = preview().json()
    lead = capture(project, source).json()
    path = '/'+project['id']+'/trend-leads/'+lead['id']
    body = {'revision': 1, 'status': 'kept', 'reason': '符合项目进一步研究目标'}
    response = C.put(ROOT+path, headers=H, json=body)
    assert response.status_code == 200 and response.json()['revision'] == 2
    assert response.json()['snapshot'] == lead['snapshot']
    assert C.put(ROOT+path, headers=H, json=body).status_code == 409
    assert C.put(ROOT+'/'+other['id']+'/trend-leads/'+lead['id'], headers=H, json=body).status_code == 404
    assert C.put(ROOT+path, headers=H, json={**body, 'revision': 2, 'snapshot': {}}).status_code == 422
    assert C.put(ROOT+path, headers=H, json={**body, 'revision': 2}).json() == response.json()
    before = database_snapshot()
    assert C.get(ROOT+'/'+project['id']+'/trend-leads').status_code == 200
    assert database_snapshot() == before


def test_missing_statistics_and_invalid_period_do_not_invent_signal():
    project = create()
    with Session.begin() as s:
        s.add(TrendSeries(id='lead-series', name='No cached statistics', query='ti:empty'))
    source = preview().json()
    assert source['snapshot']['growth'] is None
    assert source['snapshot']['signal']['x'] is None and source['snapshot']['signal']['y'] is None
    assert source['snapshot']['papers'] == []
    assert all(point['count'] is None for point in source['snapshot']['points'])
    assert capture(project, source).status_code == 200
    assert preview(period='2021').status_code == 422
    assert preview(period='bogus').status_code == 422
    assert preview(series_id='absent').status_code == 404
    assert capture(project, source, snapshot={'forged': True}).status_code == 422


def test_paper_focus_is_canonical_and_external_focus_is_provenance_not_import():
    project, aid = ready_project(); stored_trend()
    direction = preview().json()
    first = preview(paper_id='product-paper').json()
    external = preview(paper_id='external-only').json()
    assert len({direction['source_key'], first['source_key'], external['source_key']}) == 3
    assert direction['snapshot']['focus_paper_id'] is None
    assert first['snapshot']['focus_paper_id'] == 'product-paper'
    assert external['snapshot']['focus_paper_id'] == 'external-only'
    assert preview(paper_id='excluded-local').status_code == 422
    assert preview(paper_id='not-a-sample').status_code == 422
    assert capture(project, direction, focus_paper_id='product-paper').status_code == 409
    result = capture(project, external, focus_paper_id='external-only')
    assert result.status_code == 200, result.text
    assert result.json()['snapshot']['focus_paper_id'] == 'external-only'
    assert result.json()['candidate_ids'] == [] and not result.json()['source_changed']
    with Session() as s:
        assert s.get(Paper, 'external-only') is None
        assert not list(s.scalars(select(ProjectCandidate)))
    assert capture(project, first, focus_paper_id='product-paper', paper_ids=['product-paper']).status_code == 200


def test_v6_to_v7_migration_preserves_prior_data_and_missing_table_fails_closed(tmp_path):
    engine = create_engine('sqlite:///'+str(tmp_path/'trend-leads.db'))
    try:
        old = MetaData()
        for table in Base.metadata.sorted_tables:
            if table.name not in ('project_trend_leads', 'project_paper_intakes'): table.to_metadata(old)
        assert run_migrations(engine, old, MIGRATIONS[:6]) == list(range(1, 7))
        with engine.begin() as conn:
            conn.exec_driver_sql("INSERT INTO settings(key,value) VALUES ('pre-trend-lead','{}')")
        assert run_migrations(engine, Base.metadata) == [7, 8]
        assert run_migrations(engine, Base.metadata) == []
        with engine.begin() as conn:
            assert conn.exec_driver_sql("SELECT value FROM settings WHERE key='pre-trend-lead'").scalar() == '{}'
            conn.exec_driver_sql('DROP TABLE project_trend_leads')
        with pytest.raises(MigrationError, match='project_trend_leads'):
            run_migrations(engine, Base.metadata)
        assert not inspect(engine).has_table('project_trend_leads')
    finally:
        engine.dispose()

from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib

import pytest
from pypdf import PdfWriter
from sqlalchemy import MetaData, create_engine, inspect, select

from test_product_projects import C, H, ROOT, create, database_snapshot, detail
from backend.db import Analysis, Base, Domain, Job, Membership, Paper, Session, Setting
from backend.migrations import MIGRATIONS, MigrationError, run_migrations
from backend.product.models import ProjectCandidate, ProjectPaperIntake, ProjectTrendLead
from backend.product import paper_intakes as intake


@pytest.fixture(autouse=True)
def no_paid_calls(monkeypatch):
    from backend.analysis import DeepSeek
    monkeypatch.setattr(DeepSeek, 'generate', lambda *a, **k: pytest.fail('No model execution in persistence tests'))
    monkeypatch.setattr(intake, 'get_key', lambda: 'isolated-key-placeholder')
    with Session.begin() as s:
        s.merge(Setting(key='model_control', value={'enabled': False}))


def lead(project, paper='2609.12345'):
    with Session.begin() as s:
        row = ProjectTrendLead(project_id=project['id'], source_key=hashlib.sha256(project['id'].encode()).hexdigest(),
            reason='原始趋势判断依据必须完整保留', snapshot={'version': 1, 'papers': [
                {'id': paper, 'title': 'Official fixture paper', 'quote': 'Original immutable quotation.', 'relevant': True}]})
        s.add(row); s.flush()
        return copy.deepcopy({column.name: getattr(row, column.name) for column in row.__table__.columns})


def request(project, source, **changes):
    return C.post(ROOT+'/'+project['id']+'/trend-leads/'+source['id']+'/intakes', headers=H,
        json={'revision': source['revision'], 'paper_id': '2609.12345', 'domain_id': 'molecules', 'analyze': False, **changes})


def action(project, source, item, name, revision=None):
    return C.post(ROOT+'/'+project['id']+'/trend-leads/'+source['id']+'/intakes/'+item['id']+'/'+name,
        headers=H, json={'revision': item['revision'] if revision is None else revision})


def downloaded(item, version=2):
    path = intake.pdf_path(item['paper_id'], version); path.parent.mkdir(exist_ok=True)
    pdf = PdfWriter(); pdf.add_blank_page(width=612, height=792)
    pdf.write(path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return {'paper': {'id': item['paper_id'], 'version': version, 'title': 'Official fixture paper',
        'abstract': 'Official metadata', 'authors': ['Fixture'], 'categories': ['cs.LG'],
        'published': '2024-01-01T00:00:00+00:00', 'updated': '2025-01-01T00:00:00+00:00'},
        'version': version, 'sha256': sha, 'pages': 1,
        'pdf_url': 'https://arxiv.org/pdf/'+item['paper_id']+'v'+str(version),
        'metadata_url': 'https://export.arxiv.org/api/query?id_list='+item['paper_id']}


def publish(item, result=None, token='test-owner'):
    result = result or downloaded(item)
    with Session.begin() as s:
        job = s.get(Job, item['download_job_id']); job.status = 'running'
        job.result = {**job.result, 'intake_run_token': token}
    intake.finish_download(item['download_job_id'], result, token)
    with Session() as s:
        return intake.intake_view(s, s.get(ProjectPaperIntake, item['id']))


def test_concurrent_cross_project_download_is_single_and_lead_judgment_stays_frozen():
    a, b = create(), create(); la, lb = lead(a), lead(b)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda args: request(*args), [(a, la), (b, lb)]))
    assert all(response.status_code == 200 for response in responses)
    first, second = [response.json() for response in responses]
    assert first['download_job_id'] == second['download_job_id']
    assert request(a, la).json()['id'] == first['id']
    before = detail(a)['project']
    result = publish(first)
    assert result['pdf_ready'] and result['status'] == 'done' and result['actual_version'] == 2
    with Session() as s:
        assert len(list(s.scalars(select(Job).where(Job.kind == 'trend_download')))) == 1
        assert len(list(s.scalars(select(ProjectCandidate)))) == 2
        assert s.get(ProjectTrendLead, la['id']).snapshot == la['snapshot']
        assert s.get(ProjectTrendLead, la['id']).candidate_ids == []
        assert s.get(ProjectTrendLead, la['id']).revision == la['revision']
        row = s.get(ProjectPaperIntake, second['id'])
        assert row.candidate_id and row.pdf_version == 2
    assert detail(a)['project'] == before


def test_objects_revision_input_and_paused_task_reuse_are_enforced():
    a, b = create(), create(); la, lb = lead(a), lead(b)
    assert request(a, la, revision=99).status_code == 409
    assert request(b, la).status_code == 404
    assert request(a, la, paper_id='https://untrusted.invalid/a.pdf').status_code == 422
    assert request(a, la, domain_id='missing').status_code == 404
    first = request(a, la).json()
    with Session.begin() as s: s.get(Job, first['download_job_id']).status = 'paused'
    second = request(b, lb).json()
    assert second['download_job_id'] == first['download_job_id'] and second['status'] == 'paused'
    assert action(a, la, first, 'retry').status_code == 409
    assert action(b, la, first, 'analysis').status_code == 404
    with Session() as s: assert s.get(Job, first['download_job_id']).status == 'paused'


def test_download_succeeds_when_model_off_and_existing_candidate_reason_is_kept():
    project = create(); source = lead(project)
    with Session.begin() as s:
        s.add(Paper(id='2609.12345', version=2, title='Locally corrected same-version title', abstract='local',
            authors=[], categories=[], published='2024-01-01', updated='2024-01-01'))
    original = C.post(ROOT+'/'+project['id']+'/candidates', headers=H,
        json={'paper_id': '2609.12345', 'reason': '先前人工选择的候选理由'}).json()
    item = request(project, source, analyze=True).json()
    done = publish(item)
    assert done['status'] == 'done' and done['pdf_ready']
    assert done['analysis_status'] == 'blocked' and done['analysis_blocker']
    with Session() as s:
        assert s.get(Paper, item['paper_id']).title == 'Locally corrected same-version title'
        assert s.get(ProjectCandidate, done['candidate_id']).reason == original['reason']
        assert s.get(Membership, ('molecules', item['paper_id']))
        assert not list(s.scalars(select(Job).where(Job.kind == 'analyze')))
    listing = ROOT+'/'+project['id']+'/trend-leads/'+source['id']+'/intakes'
    before = database_snapshot(); response = C.get(listing)
    assert not response.json()['capabilities']['analysis_enabled']
    assert database_snapshot() == before


def test_finish_is_fenced_and_bad_result_does_not_publish_partial_records():
    project = create(); source = lead(project); item = request(project, source).json()
    result = downloaded(item)
    with Session.begin() as s:
        job = s.get(Job, item['download_job_id']); job.status = 'running'; job.result = {'intake_run_token': 'owner'}
    before = database_snapshot()
    with pytest.raises(ValueError): intake.finish_download(item['download_job_id'], result, 'wrong-owner')
    with pytest.raises(ValueError): intake.finish_download(item['download_job_id'], {**result, 'sha256': '0'*64}, 'owner')
    assert database_snapshot() == before
    with Session.begin() as s:
        job = s.get(Job, item['download_job_id']); job.result = {**job.result, 'pause_requested': True}
    with pytest.raises(ValueError): intake.finish_download(item['download_job_id'], result, 'owner')
    with Session() as s:
        assert s.get(Paper, item['paper_id']) is None
        assert s.get(ProjectPaperIntake, item['id']).candidate_id is None


def test_explicit_analysis_freezes_target_and_never_treats_job_done_as_analysis():
    project = create(); source = lead(project); item = request(project, source).json(); done = publish(item)
    with Session.begin() as s: s.merge(Setting(key='model_control', value={'enabled': True}))
    queued = action(project, source, done, 'analysis').json()
    assert queued['analysis_status'] == 'queued'
    assert queued['analysis_target']['paper_version'] == 2
    allowed, message = intake.analysis_job_allowed(queued['analysis_job_id'])
    assert allowed, message
    with Session.begin() as s:
        job = s.get(Job, queued['analysis_job_id']); job.status = 'done'; job.message = 'No analysis actually published'
    intake.reconcile()
    with Session() as s:
        row = s.get(ProjectPaperIntake, item['id'])
        assert row.analysis_id is None and row.analysis_status == 'failed'
    assert action(project, source, done, 'analysis').status_code == 409


def test_old_active_analysis_is_reused_without_running_or_reviving_it():
    project = create(); source = lead(project); item = request(project, source).json(); done = publish(item)
    with Session.begin() as s:
        s.add(Job(id='old-paused-analysis', kind='analyze', status='paused', payload={'paper_id': item['paper_id'], 'domain_id': 'molecules'}))
    response = action(project, source, done, 'analysis').json()
    assert response['analysis_job_id'] == 'old-paused-analysis'
    assert response['analysis_status'] == 'paused'
    assert not intake.analysis_job_allowed('old-paused-analysis')[0]
    with Session() as s:
        assert s.get(Job, 'old-paused-analysis').status == 'paused'
        assert len(list(s.scalars(select(Job).where(Job.kind == 'analyze')))) == 1


def test_v7_to_v8_adds_intakes_without_rewriting_old_data(tmp_path):
    engine = create_engine('sqlite:///'+str(tmp_path/'intake.db'))
    try:
        old = MetaData()
        for table in Base.metadata.sorted_tables:
            if table.name != 'project_paper_intakes': table.to_metadata(old)
        assert run_migrations(engine, old, MIGRATIONS[:7]) == list(range(1, 8))
        with engine.begin() as conn: conn.exec_driver_sql("INSERT INTO settings(key,value) VALUES ('pre-intake','{}')")
        assert run_migrations(engine, Base.metadata) == [8]
        assert run_migrations(engine, Base.metadata) == []
        with engine.begin() as conn:
            assert conn.exec_driver_sql("SELECT value FROM settings WHERE key='pre-intake'").scalar() == '{}'
            conn.exec_driver_sql('DROP TABLE project_paper_intakes')
        with pytest.raises(MigrationError, match='project_paper_intakes'): run_migrations(engine, Base.metadata)
        assert not inspect(engine).has_table('project_paper_intakes')
    finally: engine.dispose()


def test_verified_download_reuse_and_explicit_repair_of_missing_file():
    first_project, second_project = create(), create()
    first_lead, second_lead = lead(first_project), lead(second_project)
    first = publish(request(first_project, first_lead).json())
    second = request(second_project, second_lead).json()
    assert second['download_job_id'] == first['download_job_id']
    assert second['pdf_ready'] and second['candidate_id'] and second['download_reused']
    intake.pdf_path(first['paper_id'], first['actual_version']).unlink()
    third_project = create(); third_lead = lead(third_project)
    broken = request(third_project, third_lead).json()
    assert broken['status'] == 'failed' and not broken['pdf_ready']
    repaired = action(third_project, third_lead, broken, 'retry')
    assert repaired.status_code == 200
    assert repaired.json()['download_job_id'] == first['download_job_id']
    assert repaired.json()['status'] == 'queued'
    assert action(third_project, third_lead, broken, 'retry').status_code == 409
    with Session() as s:
        assert len(list(s.scalars(select(Job).where(Job.kind == 'trend_download')))) == 1


def test_changed_current_version_blocks_fixed_analysis_before_execution():
    project = create(); source = lead(project)
    done = publish(request(project, source).json())
    with Session.begin() as s: s.merge(Setting(key='model_control', value={'enabled': True}))
    queued = action(project, source, done, 'analysis').json()
    with Session.begin() as s: s.get(Paper, done['paper_id']).version = 3
    assert not intake.analysis_job_allowed(queued['analysis_job_id'])[0]
    intake.reconcile()
    with Session() as s:
        row = s.get(ProjectPaperIntake, done['id'])
        assert row.analysis_status == 'blocked' and row.analysis_id is None
        assert row.analysis_target['paper_version'] == 2
        assert row.pdf_version == 2


def test_explicit_download_bypasses_global_pause_without_reviving_old_tasks():
    project = create(); source = lead(project)
    with Session.begin() as s:
        s.merge(Setting(key='background_control', value={'paused': True}))
        s.add(Job(id='historical-paused', kind='analyze', status='paused', payload={}))
    item = request(project, source, analyze=True).json()
    with Session() as s:
        assert s.get(Job, item['download_job_id']).result['intake_explicit'] is True
    done = publish(item)
    assert done['status'] == 'done' and done['analysis_status'] == 'blocked'
    assert '模型调用已关闭' in done['analysis_blocker']
    with Session() as s:
        assert s.get(Job, 'historical-paused').status == 'paused'
        assert s.get(Setting, 'background_control').value == {'paused': True}
        assert intake.capabilities(s)['runner_paused'] is True
        s.close()
    with Session.begin() as s: s.merge(Setting(key='model_control', value={'enabled': True}))
    queued = action(project, source, done, 'analysis').json()
    assert queued['analysis_status'] == 'queued'
    with Session() as s:
        assert s.get(Job, queued['analysis_job_id']).result['intake_explicit'] is True
        assert intake.capabilities(s)['analysis_enabled'] is True
    assert intake.analysis_job_allowed(queued['analysis_job_id'])[0]


def test_unverified_pdf_identity_keeps_download_but_blocks_analysis():
    project = create(); source = lead(project)
    with Session.begin() as s: s.merge(Setting(key='model_control', value={'enabled': True}))
    item = request(project, source, analyze=True).json()
    result = {**downloaded(item), 'identity_check': {'verified': False, 'reason': 'No title or identifier on first page'}}
    done = publish(item, result)
    assert done['status'] == 'done' and done['pdf_ready']
    assert done['metadata_snapshot']['identity_check'] == result['identity_check']
    assert done['analysis_status'] == 'blocked' and '身份' in done['analysis_blocker']
    assert action(project, source, done, 'analysis').json()['analysis_status'] == 'blocked'
    with Session() as s:
        assert not list(s.scalars(select(Job).where(Job.kind == 'analyze')))

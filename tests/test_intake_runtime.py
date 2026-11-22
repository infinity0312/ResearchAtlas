"""The real scoped executor with deterministic official-source/model doubles."""
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
from sqlalchemy import select

from test_product_projects import C,H,ROOT,create
from test_project_paper_intakes import lead,request,action
from backend.db import Analysis,DATA,Domain,Job,Membership,Paper,Session,Setting,now
from backend.contracts import Extraction
from backend.product.models import ProjectCandidate,ProjectPaperIntake,ProjectTrendLead
from backend.product import intake_runtime as runtime,paper_intakes as intake

PID='2609.12345'
TITLE='Official intake fixture paper'
QUOTE='We propose a verified molecular model.'

def metadata():
    return {'id':PID,'version':2,'title':TITLE,'abstract':QUOTE,'authors':['Fixture'],
        'categories':['cs.LG'],'published':'2026-09-01T00:00:00+00:00','updated':'2026-09-02T00:00:00+00:00'}

def pdf(path,pid=PID,version=2):
    writer=PdfWriter();page=writer.add_blank_page(width=612,height=792)
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})})})
    stream=DecodedStreamObject();stream.set_data(f'BT /F1 12 Tf 50 700 Td ({TITLE}) Tj 0 -20 Td (arXiv:{pid}v{version}) Tj 0 -20 Td ({QUOTE}) Tj ET'.encode())
    page[NameObject('/Contents')]=writer._add_object(stream);writer.write(path)

@pytest.fixture(autouse=True)
def bounded(monkeypatch):
    runtime._stop.clear()
    folder=DATA/'documents'
    if folder.exists():
        for path in folder.glob(hashlib.sha256(PID.encode()).hexdigest()+'v*.pdf'):
            path.unlink()
    from backend.analysis import DeepSeek
    monkeypatch.setattr(DeepSeek,'generate',lambda *a,**k:pytest.fail('No paid generation in runtime tests'))
    monkeypatch.setattr(intake,'get_key',lambda:'fixture-key')
    with Session.begin() as s:s.merge(Setting(key='model_control',value={'enabled':False}))
    calls={'metadata':0,'pdf':0}
    def fetch(*args):calls['metadata']+=1;return metadata()
    def download(pid,version,path):calls['pdf']+=1;pdf(path,pid,version)
    monkeypatch.setattr(runtime,'fetch_metadata',fetch)
    monkeypatch.setattr(runtime,'download_pdf',download)
    yield calls
    runtime._stop.clear()

def view(item):
    with Session() as s:return intake.intake_view(s,s.get(ProjectPaperIntake,item['id']))

def test_exactly_one_download_completes_multiple_projects_under_global_pause(bounded):
    p1,p2=create(),create();l1,l2=lead(p1),lead(p2)
    with Session.begin() as s:
        s.merge(Setting(key='background_control',value={'paused':True}))
        s.add(Job(id='old-paused',kind='analyze',status='paused',payload={}))
        s.add(Job(id='old-queued',kind='ingest',status='queued',payload={}))
    a,b=request(p1,l1,analyze=True).json(),request(p2,l2).json()
    assert a['download_job_id']==b['download_job_id']
    assert runtime.process_once()
    first,second=view(a),view(b)
    assert first['pdf_ready'] and second['pdf_ready'] and first['actual_version']==2
    assert first['analysis_status']=='blocked' and first['analysis_id'] is None
    assert first['candidate_id'] and second['candidate_id']
    assert bounded=={'metadata':1,'pdf':1}
    assert not runtime.process_once()
    with Session() as s:
        assert s.get(Job,'old-paused').status=='paused' and s.get(Job,'old-queued').status=='queued'
        assert s.get(Setting,'background_control').value=={'paused':True}
        assert s.get(ProjectTrendLead,l1['id']).snapshot==l1['snapshot']
        assert s.get(ProjectTrendLead,l1['id']).reason==l1['reason']
        assert len(list(s.scalars(select(ProjectCandidate))))==2
        assert not list(s.scalars(select(Analysis)))

def test_failed_download_is_atomic_and_explicit_retry_keeps_same_job(monkeypatch,bounded):
    project=create();source=lead(project);item=request(project,source).json()
    monkeypatch.setattr(runtime,'download_pdf',lambda pid,v,path:path.write_bytes(b'not a PDF'))
    runtime.process_once();failed=view(item)
    assert failed['status']=='failed' and not failed['pdf_ready']
    with Session() as s:assert s.get(Paper,PID) is None and not list(s.scalars(select(ProjectCandidate)))
    retried=action(project,source,failed,'retry').json()
    monkeypatch.setattr(runtime,'download_pdf',lambda pid,v,path:pdf(path,pid,v))
    assert retried['download_job_id']==item['download_job_id']
    runtime.process_once();assert view(item)['pdf_ready']
    assert bounded['metadata']==1  # resolved official version survives failure

@pytest.mark.parametrize('operation,expected',[('pause','paused'),('cancel','cancelled')])
def test_pause_or_cancel_during_download_stops_before_publication(monkeypatch,operation,expected):
    project=create();source=lead(project);item=request(project,source).json()
    def download(pid,v,path):
        pdf(path,pid,v)
        assert C.post('/api/jobs/'+item['download_job_id']+'/'+operation,headers=H).status_code==200
    monkeypatch.setattr(runtime,'download_pdf',download)
    runtime.process_once();assert view(item)['status']==expected
    assert not runtime.process_once()
    with Session() as s:assert s.get(Paper,PID) is None

def test_changed_owner_cannot_publish_another_owners_result(monkeypatch):
    project=create();source=lead(project);item=request(project,source).json()
    def download(pid,v,path):
        pdf(path,pid,v)
        with Session.begin() as s:
            job=s.get(Job,item['download_job_id']);job.result={**job.result,'intake_run_token':'another-owner'}
    monkeypatch.setattr(runtime,'download_pdf',download)
    runtime.process_once()
    with Session() as s:
        assert s.get(Paper,PID) is None
        assert s.get(Job,item['download_job_id']).result['intake_run_token']=='another-owner'

def test_pdf_header_version_mismatch_never_becomes_local_source(monkeypatch):
    project=create();source=lead(project);item=request(project,source).json()
    monkeypatch.setattr(runtime,'download_pdf',lambda pid,v,path:pdf(path,pid,1))
    runtime.process_once()
    assert view(item)['status']=='failed'
    with Session() as s:assert s.get(Paper,PID) is None

def test_domain_deleted_during_network_work_cannot_leave_unowned_membership(monkeypatch):
    project=create();source=lead(project);item=request(project,source).json()
    def download(pid,v,path):
        pdf(path,pid,v)
        with Session.begin() as s:s.delete(s.get(Domain,'molecules'))
    monkeypatch.setattr(runtime,'download_pdf',download)
    runtime.process_once()
    assert view(item)['status']=='failed' and not view(item)['candidate_id']
    with Session() as s:
        assert s.get(Paper,PID) is None and s.get(Membership,('molecules',PID)) is None

def test_missing_pdf_explicit_repair_reuses_the_frozen_download_version(monkeypatch):
    project=create();source=lead(project);item=request(project,source).json();runtime.process_once()
    original=intake.pdf_path(PID,2).read_bytes();intake.pdf_path(PID,2).unlink()
    broken=view(item);assert not broken['pdf_ready']
    assert action(project,source,broken,'retry').status_code==200
    monkeypatch.setattr(runtime,'fetch_metadata',lambda *a:pytest.fail('Do not resolve a newer version during repair'))
    monkeypatch.setattr(runtime,'download_pdf',lambda pid,v,path:path.write_bytes(original))
    runtime.process_once();assert view(item)['pdf_ready'] and view(item)['pdf_version']==2

def test_analysis_requires_real_current_source_bound_result_and_keeps_review_gate(monkeypatch):
    project=create();source=lead(project)
    with Session.begin() as s:
        s.merge(Setting(key='model_control',value={'enabled':True}))
        s.merge(Setting(key='background_control',value={'paused':True}))
    item=request(project,source,analyze=True).json();runtime.process_once()
    assert view(item)['analysis_status']=='queued'
    from backend import worker
    def generate(job):
        assert job.payload['intake_target']['paper_version']==2
        digest=view(item)['pdf_sha256'];(DATA/'documents'/(digest+'.json')).write_text(json.dumps([{'page':1,'text':QUOTE}]),encoding='utf-8')
        raw={'summary':'Fixture report','methods':['Model'],'topics':[],'problems':[],
             'claims':[{'kind':'method','text':'Method','page':1,'quote':QUOTE}],
             'field_evidence':{'summary':[0],'methods.0':[0]}}
        from backend.analysis_pipeline import analyze_document
        result=analyze_document([{'page':1,'text':QUOTE}],
            SimpleNamespace(name='Fixture',topics=[],definitions=[]),
            model=SimpleNamespace(config={'model':'fixture-model'},generate=lambda prompt:copy.deepcopy(raw)))
        with Session.begin() as s:
            s.add(Analysis(paper_id=PID,domain_id='molecules',version=2,taxonomy_version=1,
                model='fixture-model',content_hash=digest,result={**result,
                    'fulltext_markdown':'# Fixture\n\n'+('Source interpretation. '*50)}))
        return {'message':'Fixture analysis completed'}
    monkeypatch.setattr(worker,'run_job',generate)
    runtime.process_once();assert view(item)['analysis_status']=='done' and view(item)['analysis_id']
    detail=C.get(ROOT+'/'+project['id']).json()
    assert not detail['readiness']['can_review'] and not detail['readiness']['can_deliver']
    assert detail['project']['revision']==project['revision']

def test_model_disabled_after_request_never_calls_worker(monkeypatch):
    project=create();source=lead(project)
    with Session.begin() as s:s.merge(Setting(key='model_control',value={'enabled':True}))
    item=request(project,source,analyze=True).json();runtime.process_once()
    with Session.begin() as s:s.get(Setting,'model_control').value={'enabled':False}
    from backend import worker
    monkeypatch.setattr(worker,'run_job',lambda *a:pytest.fail('Disabled model must never start'))
    runtime.process_once();assert view(item)['analysis_status']=='blocked' and view(item)['pdf_ready']

def test_recovery_does_not_retry_unknown_paid_attempts_or_change_old_work():
    project=create();source=lead(project);item=request(project,source).json()
    with Session.begin() as s:
        job=s.get(Job,item['download_job_id']);job.status='running';job.result={**job.result,'intake_run_token':'lost-process'}
        s.add(Job(id='old-running',kind='analyze',status='running',payload={}))
    runtime._recover()
    assert view(item)['status']=='failed' and not runtime.process_once()
    with Session() as s:assert s.get(Job,'old-running').status=='running'

def test_frozen_analysis_target_rejects_a_different_version_or_source():
    expected={'paper_version':2,'taxonomy_version':1,'content_hash':'sha','model':'m','model_identity':service_digest()}
    job=SimpleNamespace(payload={'intake_scope':True,'intake_target':expected},result={})
    runtime.assert_analysis_target(job,SimpleNamespace(version=2),SimpleNamespace(taxonomy_version=1),SimpleNamespace(config={'model':'m','base_url':'u'}),'sha')
    with pytest.raises(ValueError,match='分析目标'):
        runtime.assert_analysis_target(job,SimpleNamespace(version=3),SimpleNamespace(taxonomy_version=1),SimpleNamespace(config={'model':'m','base_url':'u'}),'sha')
    with pytest.raises(ValueError,match='分析目标'):
        runtime.assert_analysis_target(job,SimpleNamespace(version=2),SimpleNamespace(taxonomy_version=1),SimpleNamespace(config={'model':'m','base_url':'u'}),'other')

def service_digest():
    from backend.product.service import digest
    return digest({'model':'m','base_url':'u','pipeline':runtime.PIPELINE_VERSION})

import json
from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.app import app
from backend.db import Session,Note,Job,Setting,Analysis,DATA,now
from backend.workspace import sync,local_path
from backend.services import upsert_papers
c=TestClient(app);H={'X-Atlas-Client':'1'}
def post(path,data=None):return c.post('/api'+path,json=data or {},headers=H)
def note():return post('/notes',{'title':'笔记','series':'研究/方法','content':'original'}).json()
def paper():
    upsert_papers('molecules',[{'id':'p1','version':1,'title':'Paper','abstract':'source','authors':[],'categories':[],'published':now(),'updated':now()}])

def test_note_delete_restore_and_stale_delete():
    n=note()
    assert c.delete('/api/notes/'+n['id']+'?revision=2',headers=H).status_code==409
    assert c.delete('/api/notes/'+n['id']+'?revision=1',headers=H).status_code==200
    assert c.get('/api/notes/'+n['id']).status_code==404
    restored=post('/notes/'+n['id']+'/restore').json()
    assert restored['content']=='original' and restored['revision']==2

def test_repeated_save_after_lost_response_is_idempotent():
    n=note();sent={**n,'content':'saved during reload'}
    first=c.put('/api/notes/'+n['id'],headers=H,json=sent)
    repeated=c.put('/api/notes/'+n['id'],headers=H,json=sent)
    assert repeated.status_code==200 and repeated.json()['revision']==first.json()['revision']
    assert c.put('/api/notes/'+n['id'],headers=H,json={**sent,'content':'different stale draft'}).status_code==409

def test_folder_move_updates_descendants_and_revisions():
    n=note()
    assert post('/note-folders',{'path':'研究'}).status_code==409
    r=c.put('/api/note-folders',headers=H,json={'path':'研究','destination':'基础研究'})
    assert r.status_code==200
    changed=c.get('/api/notes/'+n['id']).json()
    assert changed['series']=='基础研究/方法' and changed['revision']==2
    assert c.put('/api/notes/'+n['id'],headers=H,json=n).status_code==409

def test_vault_three_way_sync_and_trash():
    n=note();sync(True)
    with Session() as s:entry=s.get(Setting,'workspace-index').value['note:'+n['id']]
    path=local_path(entry['path']);path.write_text('external',encoding='utf8')
    assert sync(True)['imported']==1
    fresh=c.get('/api/notes/'+n['id']).json();assert fresh['content']=='external'
    path.write_text('outside again',encoding='utf8')
    assert c.put('/api/notes/'+n['id'],headers=H,json={**fresh,'content':'inside again'}).status_code==200
    assert sync(True)['conflicts']
    assert path.read_text('utf8')=='outside again'
    assert c.get('/api/notes/'+n['id']).json()['content']=='inside again'
    assert c.delete('/api/notes/'+n['id']+'?revision=3',headers=H).status_code==200
    sync(True);assert not path.exists()

def test_lease_conflict_and_publication():
    paper();w=post('/collaboration',{'title':'Review','instruction':'Verify','paper_ids':['p1']}).json()
    owned=post('/collaboration/'+w['id']+'/claim',{'owner':'codex'}).json()
    assert post('/collaboration/'+w['id']+'/claim',{'owner':'other'}).status_code==409
    assert 'lease_token' not in c.get('/api/collaboration').json()[0]
    with Session.begin() as s:
        s.add(Analysis(paper_id='p1',domain_id='molecules',version=1,taxonomy_version=1,model='test',content_hash='sample',result={'summary':'new'}))
    submitted=c.put('/api/collaboration/'+w['id'],headers=H,json={'token':owned['lease_token'],'revision':owned['revision'],'markdown':'# draft'})
    assert submitted.json()['status']=='conflict'
    assert post('/collaboration/'+w['id']+'/publish',{'revision':submitted.json()['revision']}).status_code==409
    lease=post('/collaboration/'+w['id']+'/claim',{'owner':'codex'}).json()
    ready=c.put('/api/collaboration/'+w['id'],headers=H,json={'token':lease['lease_token'],'revision':lease['revision'],'markdown':'# merged'}).json()
    published=post('/collaboration/'+w['id']+'/publish',{'revision':ready['revision']}).json()
    assert c.get('/api/notes/'+published['note_id']).json()['content']=='# merged'
    assert post('/collaboration/'+w['id']+'/publish',{'revision':ready['revision']}).status_code==409

def test_delete_running_job_survives_old_worker_result_overwrite():
    with Session.begin() as s:s.add(Job(id='running',kind='analyze',payload={},status='running'))
    assert c.delete('/api/jobs/running',headers=H).status_code==200
    with Session.begin() as s:
        row=s.get(Job,'running');assert row.result['pause_requested'];row.result={};row.status='done'
    assert not c.get('/api/jobs').json()

def test_manage_duplicates_prefers_running_owner():
    with Session.begin() as s:
        s.add(Job(id='old',kind='ingest',payload={'domain_id':'molecules'},status='paused'))
        s.add(Job(id='new',kind='ingest',payload={'domain_id':'molecules'},status='running'))
    assert post('/jobs/manage').json()['duplicates_cancelled']==1
    with Session() as s:
        assert s.get(Job,'old').status=='cancelled';assert s.get(Job,'new').status=='running'
    assert post('/jobs/old/resume').status_code==409

def test_source_edits_preserve_evidence_snapshot_and_change_parser_version():
    import hashlib
    from backend.analysis import parse_pdf
    paper();documents=DATA/'documents';documents.mkdir(exist_ok=True)
    pdf=documents/(hashlib.sha256(b'p1').hexdigest()+'v1.pdf');pdf.write_bytes(b'%PDF-test-source')
    original=hashlib.sha256(pdf.read_bytes()).hexdigest()
    before=json.dumps([{'page':1,'text':'original source'}])
    (documents/(original+'.json')).write_text(before,encoding='utf8')
    with Session.begin() as s:s.add(Analysis(paper_id='p1',domain_id='molecules',version=1,taxonomy_version=1,model='test',content_hash=original,result={}))
    sync()
    with Session() as s:entry=s.get(Setting,'workspace-index').value['source:p1']
    edited=local_path(entry['path']);edited.write_text(json.dumps([{'page':1,'text':'corrected OCR'}]),encoding='utf8')
    assert sync()['imported']==1
    pages,changed=parse_pdf(pdf)
    assert changed!=original and pages[0]['text']=='corrected OCR'
    assert (documents/(original+'.json')).read_text('utf8')==before

def test_failed_math_is_escalated_once():
    paper()
    with Session.begin() as s:
        a=Analysis(paper_id='p1',domain_id='molecules',version=1,taxonomy_version=1,model='test',content_hash='test',result={'claims':[]});s.add(a);s.flush()
        s.add(Job(id='math',kind='lesson',payload={'analysis_id':a.id,'claim_index':0,'domain_id':'molecules'},status='failed',message='语义校验失败'))
    assert post('/jobs/manage').json()['escalated']==1
    assert post('/jobs/manage').json()['escalated']==0
    assert len(c.get('/api/collaboration').json())==1


def test_manual_analysis_checks_source_and_lease():
    import hashlib
    paper();content=b'%PDF-test-original';sha=hashlib.sha256(content).hexdigest()
    folder=DATA/'documents';folder.mkdir(exist_ok=True)
    (folder/(hashlib.sha256(b'p1').hexdigest()+'v1.pdf')).write_bytes(content)
    (folder/(sha+'.json')).write_text(json.dumps([{'page':1,'text':'We propose a verified molecular model.'}]),encoding='utf8')
    w=post('/collaboration',{'title':'Source review','instruction':'Verify','paper_ids':['p1']}).json()
    lease=post('/collaboration/'+w['id']+'/claim',{'owner':'codex'}).json()
    body={'token':lease['lease_token'],'revision':lease['revision'],'domain_id':'molecules','content_hash':sha,'reviewed_pages':[1],'result':{'summary':'Verified','methods':['Model'],'topics':[],'claims':[{'kind':'method','text':'Method','page':1,'quote':'A fabricated source statement.'}]}}
    route='/collaboration/'+w['id']+'/publish-analysis'
    assert post(route,body).status_code==422
    body['result']['claims'][0]['quote']='We propose a verified molecular model.'
    assert post(route,{**body,'fulltext_markdown':'Too short'}).status_code==422
    body['fulltext_markdown']='# Full-text review\n\n'+('Detailed method and experimental interpretation. '*30)
    body['review_model']='gpt-6-sol'
    wrong={**body,'content_hash':'a'*64};assert post(route,wrong).status_code==409
    result=post(route,body);assert result.status_code==200,result.text
    with Session() as s:
        analysis=s.get(Analysis,result.json()['analysis_id'])
        assert analysis.result['provenance']['source']=='codex-direct-review'
        assert analysis.result['reviewed_pages']==[1]
        assert analysis.result['fulltext_markdown']==body['fulltext_markdown']
        assert analysis.result['provenance']['review_model']=='gpt-6-sol'
    assert post(route,body).status_code==409

def test_model_disabled_before_credentials_or_network():
    from backend.analysis import DeepSeek
    import pytest
    assert post('/model-control',{'enabled':False}).status_code==200
    with pytest.raises(ValueError,match='DeepSeek'):
        DeepSeek()

def test_full_export_contains_all_tables_and_redacts_tokens():
    from backend.db import Base
    with Session.begin() as s:s.add(Setting(key='test-secret',value={'lease_token':'secret-value'}))
    result=post('/workspace/snapshot');assert result.status_code==200,result.text
    from pathlib import Path
    folder=Path(result.json()['path'])
    assert result.json()['tables']==len(Base.metadata.tables)
    settings=json.loads((folder/'settings.json').read_text('utf8'))
    assert 'secret-value' not in json.dumps(settings)
    assert c.get('/api/workspace').json()['path']==str(DATA)


def test_statistics_only_does_not_resume_paid_or_hidden_jobs():
    with Session.begin() as s:
        s.add(Job(id='count-only',kind='trends',payload={'quality':False},status='paused',result={'pause_requested':True}))
        s.add(Job(id='paid',kind='analyze',payload={},status='paused'))
    assert post('/jobs/run-statistics-only',{'ids':['paid']}).status_code==409
    assert post('/jobs/run-statistics-only',{'ids':['count-only']}).status_code==200
    with Session() as s:
        assert s.get(Job,'paid').status=='paused'
        assert s.get(Setting,'background_control').value['allowed_ids']==['count-only']


def test_macro_review_requires_complete_source_and_all_sample_ids():
    from backend.db import TrendSeries,SearchSnapshot,CatalogPaper,TrendEvidence
    with Session.begin() as s:
        s.add(TrendSeries(id='review-series',name='Review',query='cat:cs.LG',color='#123456'))
        s.add(CatalogPaper(id='macro-paper',metadata_json={'id':'macro-paper','title':'Method','abstract':'We propose a model. Scaling remains unresolved.','published':'2025-02-01'}))
        s.add(SearchSnapshot(key='complete-test',query='cat:cs.LG',start='2025-01-01',end='2025-12-31',paper_ids=['macro-paper'],source='test',complete=True))
    packet=c.get('/api/trends/review-packet?series_id=review-series&year=2025').json()
    assert packet['population']==1
    w=post('/collaboration',{'kind':'curation','title':'Macro review','instruction':'Read evidence','paper_ids':[]}).json()
    lease=post('/collaboration/'+w['id']+'/claim',{'owner':'codex'}).json()
    body={'work_id':w['id'],'token':lease['lease_token'],'revision':lease['revision'],'series_id':'review-series','year':2025,'source_hash':packet['source_hash'],'papers':[]}
    assert post('/trends/publish-review',body).status_code==422
    body['papers']=[{'id':'macro-paper','novelty':55,'rigor':40,'headroom':None,'headroom_evidence':None,'family':'Transformer','bottleneck':'No quantified opportunity assessment','evidence_index':0}]
    wrong={**body,'source_hash':'stale'};assert post('/trends/publish-review',wrong).status_code==409
    result=post('/trends/publish-review',body);assert result.status_code==200,result.text
    with Session() as s:
        saved=s.get(TrendEvidence,result.json()['trend_review_key']).result
        assert saved['papers'][0]['headroom'] is None
        assert saved['papers'][0]['quote']=='We propose a model.'
    assert post('/trends/publish-review',body).status_code==409


def test_full_index_derives_months_years_and_zeros_without_llm(monkeypatch):
    from backend.trends import run_trends,key
    from backend.db import TrendCount
    from types import SimpleNamespace
    import backend.history
    monkeypatch.setattr(backend.history,'collect',lambda *args:([{'published':'2024-02-01T00:00:00+00:00'},{'published':'2025-07-01T00:00:00+00:00'}],'source'))
    job=SimpleNamespace(id='test',payload={'start':'2024','end':'2025','interval':'year','full_index':True,'quality':False,'series':[{'name':'Test','query':'cat:cs.LG'}]})
    assert run_trends(job,lambda *args:None)['complete']
    with Session() as s:
        assert s.get(TrendCount,key('cat:cs.LG','202401010000','202412312359')).count==1
        assert s.get(TrendCount,key('cat:cs.LG','202401010000','202401312359')).count==0
        assert s.get(TrendCount,key('cat:cs.LG','202507010000','202507312359')).count==1


def test_classification_amendment_preserves_analysis_and_rejects_stale_evidence():
    import hashlib
    from backend.db import Domain
    paper();content=b'%PDF-classification';sha=hashlib.sha256(content).hexdigest()
    folder=DATA/'documents';folder.mkdir(exist_ok=True)
    (folder/(hashlib.sha256(b'p1').hexdigest()+'v1.pdf')).write_bytes(content)
    quote='We predict molecular properties with a neural model.'
    (folder/(sha+'.json')).write_text(json.dumps([{'page':1,'text':quote}]),encoding='utf8')
    original={'summary':'Detailed existing review','topics':[],'methods':['graph neural network'],'claims':[], 'reviewed_pages':[1,2,3], 'section_summaries':['preserved'], 'coverage':'existing'}
    with Session.begin() as s:
        d=s.get(Domain,'molecules');topic=d.topics[0]
        a=Analysis(paper_id='p1',domain_id=d.id,version=1,taxonomy_version=d.taxonomy_version,model='original',content_hash=sha,result=original);s.add(a);s.flush();aid=a.id
    w=post('/collaboration',{'title':'Classification','instruction':'Review source','paper_ids':['p1']}).json()
    lease=post('/collaboration/'+w['id']+'/claim',{'owner':'codex'}).json()
    body={'token':lease['lease_token'],'revision':lease['revision'],'domain_id':'molecules','analysis_id':aid,'content_hash':sha,'topics':[topic],'page':1,'quote':quote,'rationale':'The source studies molecular properties.'}
    route='/collaboration/'+w['id']+'/publish-classification'
    assert post(route,{**body,'quote':'Fabricated classification evidence.'}).status_code==422
    assert post(route,{**body,'topics':['invalid']}).status_code==422
    assert post(route,{**body,'analysis_id':aid+9}).status_code==409
    assert post(route,{**body,'content_hash':'a'*64}).status_code==409
    result=post(route,body);assert result.status_code==200,result.text
    with Session() as s:
        amended=s.get(Analysis,result.json()['analysis_id'])
        assert s.get(Analysis,aid).result==original
        for key in ('claims','reviewed_pages','section_summaries','coverage','summary'):assert amended.result[key]==original[key]
        assert amended.result['topics']==[topic]
    assert post(route,body).status_code==409


def test_cross_domain_classification_keeps_full_review():
    import hashlib
    from backend.db import Domain,Membership
    paper();raw=b'%PDF-cross-domain';sha=hashlib.sha256(raw).hexdigest();folder=DATA/'documents';folder.mkdir(exist_ok=True)
    (folder/(hashlib.sha256(b'p1').hexdigest()+'v1.pdf')).write_bytes(raw)
    quote='We train a general foundation model using low precision arithmetic.'
    (folder/(sha+'.json')).write_text(json.dumps([{'page':1,'text':quote}]),encoding='utf8')
    with Session.begin() as s:
        d=s.get(Domain,'ml');topic=d.topics[0];s.add(Membership(domain_id='ml',paper_id='p1'))
        a=Analysis(paper_id='p1',domain_id='molecules',version=1,taxonomy_version=1,model='original',content_hash=sha,result={'fulltext_markdown':'preserve','topics':[],'methods':['FP8'],'claims':[]});s.add(a);s.flush();aid=a.id
    w=post('/collaboration',{'title':'Cross domain','instruction':'Review','paper_ids':['p1']}).json();lease=post('/collaboration/'+w['id']+'/claim',{'owner':'codex'}).json()
    body={'token':lease['lease_token'],'revision':lease['revision'],'domain_id':'ml','analysis_id':aid,'content_hash':sha,'topics':[topic],'page':1,'quote':quote,'rationale':'General model training is a central contribution.'}
    r=post('/collaboration/'+w['id']+'/publish-classification',body);assert r.status_code==200,r.text
    with Session() as s:
        a=s.get(Analysis,r.json()['analysis_id']);assert a.domain_id=='ml';assert a.result['fulltext_markdown']=='preserve';assert a.result['classification_review']['source_domain_id']=='molecules'


def test_generation_and_review_provenance_are_distinct():
    import hashlib
    paper();raw=b'%PDF-model-review';sha=hashlib.sha256(raw).hexdigest();folder=DATA/'documents';folder.mkdir(exist_ok=True)
    (folder/(hashlib.sha256(b'p1').hexdigest()+'v1.pdf')).write_bytes(raw)
    quote='We propose a verified molecular model.';(folder/(sha+'.json')).write_text(json.dumps([{'page':1,'text':quote}]),encoding='utf8')
    w=post('/collaboration',{'title':'Review model draft','instruction':'Verify','paper_ids':['p1']}).json();lease=post('/collaboration/'+w['id']+'/claim',{'owner':'codex'}).json()
    body={'token':lease['lease_token'],'revision':lease['revision'],'domain_id':'molecules','content_hash':sha,'reviewed_pages':[1],'generation_model':'deepseek-chat','review_model':'codex','fulltext_markdown':'Detailed source analysis. '*70,'result':{'summary':'Verified','methods':['Model'],'topics':[],'claims':[{'kind':'method','text':'Method','page':1,'quote':quote}]}}
    r=post('/collaboration/'+w['id']+'/publish-analysis',body);assert r.status_code==200,r.text
    with Session() as s:
        a=s.get(Analysis,r.json()['analysis_id']);assert a.result['provenance']['generation_model']=='deepseek-chat';assert a.result['provenance']['review_model']=='codex';assert 'deepseek-chat' in a.model

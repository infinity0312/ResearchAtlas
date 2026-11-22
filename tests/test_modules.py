from datetime import datetime,timezone
from types import SimpleNamespace
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from backend.app import app
from backend.db import *
from backend.sources import parse_atom
from backend.services import upsert_papers,enqueue
from backend.analysis import chunks,verified_claims,analyze_document
from backend.worker import run_job

client=TestClient(app)
HEAD={'X-Atlas-Client':'1'}
def paper(version=1):
    return {'id':'2609.12345','version':version,'title':'Equivariant molecular models','abstract':'A scientific learning method.','authors':['A. Researcher'],'categories':['cs.LG','q-bio.BM'],'published':now(),'updated':now()}

def test_cross_domain_and_versions_preserve_user_state():
    upsert_papers('molecules',[paper()])
    with Session.begin() as s: s.get(Paper,'2609.12345').saved=True
    upsert_papers('life',[paper(2)])
    upsert_papers('molecules',[paper(1)])
    with Session() as s:
        assert s.scalar(select(func.count()).select_from(Paper))==1
        assert s.scalar(select(func.count()).select_from(Version))==2
        assert s.scalar(select(func.count()).select_from(Membership))==2
        assert s.get(Paper,'2609.12345').version==2
        assert s.get(Paper,'2609.12345').saved

def test_atom_safe_and_version_aware():
    xml='''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:o="http://a9.com/-/spec/opensearch/1.1/"><o:totalResults>1</o:totalResults><entry><id>http://arxiv.org/abs/2609.12345v3</id><title>New paper</title><summary>Abstract</summary><published>2026-09-01T00:00:00Z</published><updated>2026-09-24T00:00:00Z</updated><author><name>A</name></author><category term="cs.LG"/></entry></feed>'''
    rows,total=parse_atom(xml)
    assert total==1 and rows[0]['version']==3 and rows[0]['id']=='2609.12345'

def test_chunks_do_not_truncate_long_pages():
    pages=[{'page':1,'text':'x'*40000},{'page':2,'text':'y'*20}]
    result=chunks(pages,16000)
    assert sum(len(p['text']) for b in result for p in b)==40020
    assert all(sum(len(p['text']) for p in b)<=16000 for b in result)

def test_evidence_rejects_fabricated_quotes():
    pages=[{'page':1,'text':'We use an equivariant graph network for molecular prediction.'}]
    claims=[{'page':1,'quote':'equivariant graph network'},{'page':2,'quote':'equivariant graph network'},{'page':1,'quote':'unprecedented accuracy'}]
    assert len(verified_claims(claims,pages))==1

def test_model_pipeline_uses_schema_taxonomy_and_evidence():
    class Fake:
        def generate(self,prompt):
            return {'summary':'方法概要','topics':['性质预测','不存在的类别'],'methods':['GNN'],'field_evidence':{'summary':[0],'topics.0':[0],'methods.0':[0]},'claims':[{'kind':'method','text':'等变图网络','page':1,'quote':'equivariant graph network','basis':'author'},{'kind':'limitation','text':'错误结论','page':1,'quote':'a totally fabricated quotation','basis':'author'}]}
    output=analyze_document([{'page':1,'text':'We use an equivariant graph network for molecular prediction.'}],SimpleNamespace(name='分子',topics=['性质预测']),model=Fake())
    assert output['topics']==['性质预测']
    assert len(output['claims'])==1 and output['rejected_evidence']==1

def test_job_deduplication():
    a=enqueue('ingest',{'domain_id':'life'})
    b=enqueue('ingest',{'domain_id':'life'})
    assert a==b

def test_schema_retry_explains_confused_kind_and_basis():
    class CorrectingModel:
        calls=0
        def generate(self,prompt):
            self.calls+=1
            if self.calls==2:
                assert 'Do not rewrite text or evidence' in prompt
                return {'repairs':[{'index':0,'kind':'limitation'}]}
            return {'summary':'Test','claims':[{'kind':'observation' if self.calls==1 else 'limitation','basis':'observation','text':'Only molecular data were evaluated.','page':1,'quote':'We evaluate only molecular data.'}]}
    model=CorrectingModel()
    result=analyze_document([{'page':1,'text':'We evaluate only molecular data.'}],SimpleNamespace(name='Test',topics=[]),model=model)
    assert model.calls==2 and result['claims'][0]['kind']=='limitation'

def test_survey_allows_empty_bibliography_segment():
    class NarrativeOnly:
        def generate(self,prompt):
            assert 'bibliography' in prompt
            if 'References only' in prompt: return {'topics':[]}
            return {'topics':[{'name':'Design','definition':'Design of materials','page':1,'quote':'Materials design explores new structures.'}]}
    pages=[{'page':1,'text':'Materials design explores new structures.'+' '*15950},{'page':2,'text':'References only: [1] A study of unrelated topics.'}]
    out=analyze_document(pages,SimpleNamespace(name='Materials',topics=[]),survey=True,model=NarrativeOnly())
    assert len(out['topics'])==1 and out['topics'][0]['page']==1

def test_completed_segments_are_reused_after_failure(tmp_path):
    class Interruptible:
        calls=0
        fail=True
        def generate(self,prompt):
            self.calls+=1
            if 'Second segment' in prompt:
                if self.fail: raise RuntimeError('connection lost')
                return {'summary':'Second','claims':[]}
            return {'summary':'First','claims':[{'kind':'method','text':'Method','page':1,'quote':'First segment uses graph models.'}]}
    model=Interruptible()
    pages=[{'page':1,'text':'First segment uses graph models.'+' '*15960},{'page':2,'text':'Second segment is supplementary.'}]
    domain=SimpleNamespace(name='Test',topics=[])
    import pytest
    with pytest.raises(RuntimeError): analyze_document(pages,domain,model=model,cache_dir=tmp_path)
    assert model.calls==2
    model.fail=False
    result=analyze_document(pages,domain,model=model,cache_dir=tmp_path)
    assert model.calls==3 and len(result['claims'])==1

def test_global_synthesis_keeps_only_selected_original_evidence():
    class Model:
        def generate(self,prompt):
            if prompt.startswith('Synthesize'):
                return {'summary':[{'text':'Core contribution','claim_indices':[0]}],'topics':[{'text':'Prediction','claim_indices':[0]}],'methods':[{'text':'GNN','claim_indices':[0]}],'selected_claims':[0]}
            return {'summary':'Segment','topics':['Prediction'],'claims':[{'kind':'method','text':'Graph model','page':1,'quote':'First segment uses graph models.'}]}
    pages=[{'page':1,'text':'First segment uses graph models.'+' '*15960},{'page':2,'text':'Second segment is supplementary.'}]
    result=analyze_document(pages,SimpleNamespace(name='Materials',topics=['Prediction']),model=Model(),synthesize=True)
    assert result['summary']=='Core contribution' and result['topics']==['Prediction']
    assert result['claims']==[result['all_claims'][0]]

def test_generic_domain_and_taxonomy_version():
    payload={'name':'经济学','query':'cat:econ.EM','topics':['因果推断'],'auto_sync':False}
    r=client.post('/api/domains',json=payload,headers=HEAD)
    assert r.status_code==200
    did=r.json()['id']; payload['topics']=['计量方法']
    r=client.put('/api/domains/'+did,json=payload,headers=HEAD)
    assert r.json()['taxonomy_version']==2

def test_api_query_saved_and_state():
    upsert_papers('life',[paper()])
    assert client.get('/api/papers?q=equivariant').json()['total']==1
    assert client.get('/api/papers?q=unknown').json()['total']==0
    client.patch('/api/paper/state?id=2609.12345',json={'saved':True},headers=HEAD)
    assert client.get('/api/papers?saved=true').json()['total']==1
    assert client.get('/api/overview?domain_id=life').json()['total']==1

def test_local_mutations_and_key_privacy():
    assert client.post('/api/ingest',json={'domain_id':'life'}).status_code==403
    assert client.post('/api/ingest',json={'domain_id':'life'},headers={**HEAD,'Origin':'https://evil.example'}).status_code==403
    assert 'api_key' not in client.get('/api/settings').json()
    assert client.post('/api/settings/test',headers=HEAD).status_code==409

def test_upload_rejects_invalid_pdf():
    r=client.post('/api/surveys',data={'domain_id':'life'},files={'file':('bad.pdf',b'<script>bad</script>','application/pdf')},headers=HEAD)
    assert r.status_code==422

def test_ingestion_watermark_on_success(monkeypatch):
    monkeypatch.setattr('backend.worker.ArxivSource.fetch',lambda *args:([paper()],1))
    j=SimpleNamespace(id=enqueue('ingest',{'domain_id':'life','days':30}),kind='ingest',payload={'domain_id':'life','days':30})
    result=run_job(j)
    assert result['new']==1
    with Session() as s: assert s.get(Domain,'life').last_sync

def test_failed_source_does_not_advance_watermark(monkeypatch):
    def fail(*args): raise RuntimeError('network')
    monkeypatch.setattr('backend.worker.ArxivSource.fetch',fail)
    monkeypatch.setattr('backend.worker.ArxivRssSource.fetch_daily',fail)
    j=SimpleNamespace(id=enqueue('ingest',{'domain_id':'life'}),kind='ingest',payload={'domain_id':'life'})
    import pytest
    with pytest.raises(RuntimeError): run_job(j)
    with Session() as s: assert not s.get(Domain,'life').last_sync

def test_stale_analysis_excluded_from_trends():
    upsert_papers('life',[paper(2)])
    with Session.begin() as s:
        s.add(Analysis(paper_id='2609.12345',domain_id='life',version=1,taxonomy_version=1,model='test',content_hash='hash',result={'topics':['蛋白质设计'],'methods':['GNN']}))
    assert client.get('/api/overview?domain_id=life').json()['analyzed']==0

def test_rss_query_boolean_and_date_basis():
    from backend.sources import matches_query,parse_rss
    p=paper()
    assert matches_query('(cat:q-bio.BM OR cat:cs.AI) AND all:"learning"',p)
    assert not matches_query('cat:cs.LG ANDNOT all:"learning"',p)
    xml='''<rss><channel><item><guid>oai:arXiv.org:2609.12345v2</guid><title>Title</title><description>Abstract: text</description><pubDate>Fri, 25 Sep 2026 00:00:00 -0400</pubDate><category>cs.LG</category></item></channel></rss>'''
    row=parse_rss(xml)[0]
    assert row['date_basis']=='announcement' and row['version']==2

def test_rss_cannot_replace_known_submission_date():
    p=paper();p['published']='2024-01-01T00:00:00+00:00';upsert_papers('life',[p])
    p2=paper(2);p2['date_basis']='announcement';upsert_papers('life',[p2])
    with Session() as s:
        p=s.get(Paper,'2609.12345');assert p.published.startswith('2024') and p.date_basis=='submitted'

def test_survey_definition_published_and_given_to_classifier():
    topic={'name':'结构生成','definition':'从条件生成三维分子结构','page':1,'quote':'conditional molecular structure generation'}
    with Session.begin() as s:
        s.add(Survey(id='survey-test',domain_id='molecules',title='Test survey',filename='test.pdf',status='draft',draft={'topics':[topic]}))
    assert client.post('/api/surveys/survey-test/publish',headers=HEAD).status_code==200
    with Session() as s: domain=s.get(Domain,'molecules')
    assert domain.taxonomy_version==2 and domain.definitions==[topic]
    class Fake:
        def generate(self,prompt):
            assert '从条件生成三维分子结构' in prompt
            return {'summary':'测试','topics':['结构生成'],'methods':[],'field_evidence':{'summary':[0],'topics.0':[0]},'claims':[{'kind':'method','text':'方法','page':1,'quote':'conditional molecular structure generation','basis':'author'}]}
    out=analyze_document([{'page':1,'text':topic['quote']}],domain,model=Fake())
    assert out['topics']==['结构生成']

def test_concurrent_enqueue_is_idempotent():
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=5) as pool:
        ids=list(pool.map(lambda _:enqueue('ingest',{'domain_id':'life'}),range(10)))
    assert len(set(ids))==1

def test_overview_cache_invalidates_after_user_mutation():
    upsert_papers('life',[paper()])
    assert client.get('/api/overview?domain_id=life').json()['saved']==0
    client.patch('/api/paper/state?id=2609.12345',json={'saved':True},headers=HEAD)
    assert client.get('/api/overview?domain_id=life').json()['saved']==1

def test_auto_analysis_respects_daily_task_budget(monkeypatch):
    from backend.worker import queue_candidates
    monkeypatch.setattr('backend.worker.get_key',lambda:'test-not-a-real-key')
    with Session.begin() as s:
        row=s.get(Setting,'llm');row.value={**row.value,'auto_analyze':True,'daily_limit':1}
    with Session() as s: d=s.get(Domain,'life')
    queue_candidates(d,[paper(),{**paper(),'id':'2609.12346'}])
    with Session() as s: assert s.scalar(select(func.count()).select_from(Job).where(Job.kind=='analyze'))==1

def test_deepseek_adapter_validates_transport_output(monkeypatch):
    import httpx
    from backend.analysis import DeepSeek
    monkeypatch.setattr('backend.analysis.get_key',lambda:'test-not-a-real-key')
    def post(url,**kwargs):
        assert url=='https://api.deepseek.com/chat/completions'
        assert kwargs['json']['response_format']=={'type':'json_object'}
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':'{"connected":true}'}}]})
    monkeypatch.setattr('backend.analysis._client.post',post)
    assert DeepSeek().generate('Return JSON')['connected'] is True

def test_current_topic_and_method_filter_match_same_analysis():
    upsert_papers('life',[paper(2)])
    with Session.begin() as s:
        for version,method in [(1,'OldMethod'),(2,'NewMethod')]:
            s.add(Analysis(paper_id='2609.12345',domain_id='life',version=version,taxonomy_version=1,model='test',content_hash='hash',result={'topics':['蛋白质设计'],'methods':[method],'summary':'test'}))
    assert client.get('/api/papers?topic=蛋白质设计&method=OldMethod').json()['total']==0
    assert client.get('/api/papers?topic=蛋白质设计&method=NewMethod').json()['total']==1

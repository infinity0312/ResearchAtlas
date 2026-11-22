import copy
from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.app import app
from backend.db import Analysis, Paper, Session, now

client=TestClient(app)
headers={'X-Atlas-Client':'1'}

def setup_analysis():
    with Session.begin() as s:
        s.add(Paper(id='edit-test',title='Editable paper',abstract='',authors=[],categories=[],published=now(),updated=now()))
        a=Analysis(paper_id='edit-test',domain_id='molecules',version=1,taxonomy_version=1,model='gpt-6.1-sol',content_hash='old-source',result={'summary':'Original summary','fulltext_markdown':'## Original\nBody','topics':[],'methods':[],'problems':[],'claims':[{'text':'Original claim','kind':'method','basis':'author','page':2,'quote':'Immutable source'}],'pages':4,'coverage':'complete','rejected_evidence':0,'section_summaries':[],'grounding':{'summary':[]},'prompt_version':'evidence-v10-grounded-presentation'})
        s.add(a);s.flush();return a.id,copy.deepcopy(a.result)

def body(aid):
    return {'base_analysis_id':aid,'summary':'Revised summary','fulltext_markdown':'## Revised\n$E=mc^2$','claim_texts':['Revised claim']}

def test_edit_preserves_old_source_and_creates_readable_version():
    aid,old=setup_analysis()
    response=client.post(f'/api/analysis/{aid}/edit',headers=headers,json=body(aid))
    assert response.status_code==200,response.text
    new=response.json();assert new['id']!=aid
    assert new['quality']['semantic']=='not_reviewed'
    assert new['result']['editorial_edit']['base_analysis_id']==aid
    assert 'grounding' not in new['result']
    assert new['result']['claims'][0]['quote']=='Immutable source'
    assert new['result']['claims'][0]['page']==2
    with Session() as s:
        assert s.get(Analysis,aid).result==old
        current=s.get(Analysis,new['id'])
        assert current.content_hash=='old-source' and current.model=='gpt-6.1-sol'
    assert client.get('/api/paper',params={'id':'edit-test','domain_id':'molecules'}).json()['analysis']['id']==new['id']
    history=client.get('/api/analysis/history',params={'paper_id':'edit-test','domain_id':'molecules'}).json()
    assert [v['id'] for v in history]==[new['id'],aid]
    assert client.get(f'/api/analysis/{aid}/version').json()['result']==old

def test_competing_edit_cannot_overwrite_and_noop_does_not_create_row():
    aid,old=setup_analysis()
    noop={'base_analysis_id':aid,'summary':old['summary'],'fulltext_markdown':old['fulltext_markdown'],'claim_texts':[old['claims'][0]['text']]}
    assert client.post(f'/api/analysis/{aid}/edit',headers=headers,json=noop).json()['id']==aid
    assert client.post(f'/api/analysis/{aid}/edit',headers=headers,json=body(aid)).status_code==200
    assert client.post(f'/api/analysis/{aid}/edit',headers=headers,json=body(aid)).status_code==409
    with Session() as s:assert len(list(s.scalars(select(Analysis))))==2

def test_reject_empty_summary_changed_claim_count_and_missing_client_header():
    aid,_=setup_analysis()
    assert client.post(f'/api/analysis/{aid}/edit',json=body(aid)).status_code==403
    invalid=body(aid);invalid['summary']='  '
    assert client.post(f'/api/analysis/{aid}/edit',headers=headers,json=invalid).status_code==422
    invalid=body(aid);invalid['claim_texts']=[]
    assert client.post(f'/api/analysis/{aid}/edit',headers=headers,json=invalid).status_code==422

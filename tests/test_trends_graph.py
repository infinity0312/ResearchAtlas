from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app import app
from backend.db import *
from backend.services import upsert_papers
from backend.trends import buckets,run_trends,count_remote
from backend.graph_labels import acronym
from backend.method_families import family
from sqlalchemy import select,func
import httpx,pytest
c=TestClient(app);H={'X-Atlas-Client':'1'}
def seed():
    upsert_papers('molecules',[dict(id='2609.00001',version=1,title='Graph neural networks',abstract='',authors=[],categories=[],published=now(),updated=now())])
    with Session.begin() as s:s.add(Analysis(paper_id='2609.00001',domain_id='molecules',version=1,taxonomy_version=1,model='test',content_hash='test',result={'methods':['GNN','Graph neural network','MAE'],'topics':['性质预测']}))
def test_acronym_and_saved_override():
    seed();assert acronym('Graph Neural Network','')=='GNN';assert acronym('AIDEN','')=='AIDEN'
    assert c.put('/api/paper/graph-label',params={'id':'2609.00001'},headers=H,json={'label':'MyGNN'}).status_code==200
    with Session() as s:assert s.get(GraphLabel,'2609.00001').label=='MyGNN'
    assert c.put('/api/paper/graph-label',params={'id':'2609.00001'},headers=H,json={'label':'two words'}).status_code==422
    assert c.put('/api/paper/graph-label',params={'id':'missing'},headers=H,json={'label':'x'}).status_code==404
    c.put('/api/paper/graph-label',params={'id':'2609.00001'},headers=H,json={'label':''})
    with Session() as s:assert s.get(GraphLabel,'2609.00001').label==''
def test_method_family_deduplicates_and_can_be_corrected():
    seed();d=c.get('/api/method-matrix').json();assert d['papers'][0]['families']==['图神经网络'];assert len(d['papers'])==1
    c.put('/api/method-families',headers=H,json={'method':'GNN','family':'我的方法家族'})
    d=c.get('/api/method-matrix').json();assert '我的方法家族' in d['papers'][0]['families']
    assert family('unrecognized',{})=='待归类'
def test_trends_calendar_validation_and_empty_is_not_zero():
    assert buckets('2024-02','2024-03','month')[0][2]=='202402292359'
    assert buckets('2023','2024','year')[1][1]=='202401010000'
    for a,b,i in [('2024-13','2025-01','month'),('2026','2020','year'),('1900','2020','year')]:
        with pytest.raises(ValueError):buckets(a,b,i)
    d=c.get('/api/trends/data',params={'ids':'preset-0','start':'2020','end':'2021'}).json()
    assert [p['count'] for p in d['series'][0]['points']]==[None,None]
    assert d['series'][0]['growth'] is None
    assert c.post('/api/trends/refresh',headers=H,json={'ids':['unknown'],'start':'2020','end':'2021'}).status_code==404

def test_cached_macro_counts_independent_of_library_and_query_version():
    r=c.post('/api/trends/refresh',headers=H,json={'ids':['preset-0'],'start':'2020','end':'2021'});assert r.status_code==202
    with Session() as s:j=s.get(Job,r.json()['job_id'])
    with patch('backend.trends.count_remote',side_effect=[100,130]) as remote:
        run_trends(j,lambda *a:None);assert remote.call_count==2
        run_trends(j,lambda *a:None);assert remote.call_count==2
    d=c.get('/api/trends/data',params={'ids':'preset-0','start':'2020','end':'2021'}).json()['series'][0]
    assert d['growth']==30 and d['points'][0]['count']==100
    with Session() as s:assert s.scalar(select(func.count()).select_from(Paper))==0
    c.put('/api/trends/series/preset-0',headers=H,json={'name':'改名','query':'ti:changed'})
    d=c.get('/api/trends/data',params={'ids':'preset-0','start':'2020','end':'2021'}).json()['series'][0]
    assert all(p['count'] is None for p in d['points'])

def test_remote_response_validation_and_failure_preserves_unknown():
    with patch('backend.trends.arxiv_wait'),patch('backend.trends.httpx.get',return_value=httpx.Response(200,text='<feed xmlns="http://www.w3.org/2005/Atom"/>',request=httpx.Request('GET','https://export.arxiv.org'))):
        with pytest.raises(ValueError):count_remote('ti:foo')
    with patch('backend.trends.arxiv_wait'),patch('backend.trends.httpx.get',return_value=httpx.Response(406,request=httpx.Request('GET','https://export.arxiv.org'))):
        with pytest.raises(RuntimeError,match='406'):count_remote('ti:foo')

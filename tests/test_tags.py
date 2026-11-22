from fastapi.testclient import TestClient
from backend.app import app
from backend.db import *
from backend.services import upsert_papers
from backend.tags import import_result
from sqlalchemy import select
c=TestClient(app);H={'X-Atlas-Client':'1'}
def seed():
    upsert_papers('molecules',[dict(id=f'2609.{i:05}',version=1,title=f'Paper {i}',abstract='',authors=[],categories=[],published=now(),updated=now()) for i in range(3)])
def create(name,kind='method'):
    r=c.post('/api/tags',headers=H,json={'name':name,'kind':kind});assert r.status_code==201;return r.json()['id']
def link(p,t,removed=False):
    assert c.put(f'/api/paper/tags/{t}',params={'id':p,'removed':removed},headers=H).status_code==200
def test_graph_any_all_excludes_unselected_nodes_and_limits():
    seed();a=create('GNN');b=create('Prediction','problem');hidden=create('Hidden')
    link('2609.00000',a);link('2609.00000',b);link('2609.00000',hidden);link('2609.00001',a)
    assert c.get('/api/graph').json()['papers']==[]
    g=c.get('/api/graph',params=[('tag_ids',a),('tag_ids',b)]).json()
    assert len(g['papers'])==2 and {t['id'] for t in g['tags']}=={a,b}
    assert all(e['tag_id']!=hidden for e in g['links'])
    g=c.get('/api/graph',params=[('tag_ids',a),('tag_ids',b),('match','all')]).json()
    assert [p['id'] for p in g['papers']]==['2609.00000']
    g=c.get('/api/graph',params={'tag_ids':a,'limit':1}).json()
    assert g['total']==2 and g['truncated'] and len(g['papers'])==1
    assert c.get('/api/graph',params={'tag_ids':a,'domain_id':'life'}).json()['papers']==[]
def test_rename_archive_restore_and_removed_auto_tags_survive_import():
    seed()
    with Session.begin() as s: import_result(s,'2609.00000',{'methods':['GNN']})
    t=c.get('/api/tags').json()[0];tid=t['id']
    assert c.put('/api/tags/'+tid,headers=H,json={**t,'name':'Graph neural network'}).status_code==200
    with Session.begin() as s: import_result(s,'2609.00000',{'methods':['GNN']})
    assert len(c.get('/api/tags').json())==1
    link('2609.00000',tid,True)
    with Session.begin() as s: import_result(s,'2609.00000',{'methods':['GNN']})
    assert c.get('/api/paper/tags',params={'id':'2609.00000'}).json()==[]
    link('2609.00000',tid)
    payload={'name':'Graph neural network','kind':'method','archived':True}
    c.put('/api/tags/'+tid,headers=H,json=payload)
    assert c.get('/api/graph',params={'tag_ids':tid}).json()['papers']==[]
    c.put('/api/tags/'+tid,headers=H,json={**payload,'archived':False})
    assert len(c.get('/api/graph',params={'tag_ids':tid}).json()['papers'])==1
def test_tag_validation_and_normalized_uniqueness():
    seed();create('GNN')
    assert c.post('/api/tags',headers=H,json={'name':' gnn '}).status_code==409
    assert c.post('/api/tags',headers=H,json={'name':'   '}).status_code==422
    assert c.post('/api/tags',headers=H,json={'name':'x','kind':'bogus'}).status_code==422
    assert c.put('/api/paper/tags/missing',headers=H,params={'id':'2609.00000'}).status_code==404

def test_problem_import_and_time_filter():
    seed()
    with Session.begin() as s:
        import_result(s,'2609.00000',{'problems':['Charge density prediction']})
        s.get(Paper,'2609.00000').published='2020-01-01T00:00:00+00:00'
    t=c.get('/api/tags').json()[0]
    assert t['kind']=='problem'
    assert c.get('/api/graph',params={'tag_ids':t['id'],'days':30}).json()['papers']==[]
    assert len(c.get('/api/graph',params={'tag_ids':t['id']}).json()['papers'])==1
def test_graph_all_tags_exclusions_and_empty_selection():
    seed();a=create('All A');b=create('All B');link('2609.00000',a);link('2609.00001',b)
    g=c.get('/api/graph',params={'all_tags':True}).json();assert len(g['papers'])==2
    g=c.get('/api/graph',params={'all_tags':True,'excluded_ids':a}).json();assert [p['id'] for p in g['papers']]==['2609.00001']
    assert c.get('/api/graph',params={'all_tags':False}).json()['papers']==[]

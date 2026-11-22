import json
import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend.db import *
from backend.services import upsert_papers
from backend.lessons import build_lesson
c=TestClient(app);H={'X-Atlas-Client':'1'}

def test_notes_roundtrip_conflict_archive_and_links():
    n=c.post('/api/notes',headers=H,json={'title':'数学笔记','series':'方法','content':'# Hello\n\n$$x^2$$'}).json()
    other=c.post('/api/notes',headers=H,json={'title':'另一篇','content':'见 [[数学笔记]]'}).json()
    assert c.get('/api/notes/'+n['id']).json()['backlinks']==[{'id':other['id'],'title':other['title']}]
    assert 'content' not in c.get('/api/notes').json()[0]
    r=c.put('/api/notes/'+n['id'],headers=H,json={**n,'content':'new','archived':True});assert r.status_code==200
    assert c.put('/api/notes/'+n['id'],headers=H,json=n).status_code==409
    assert c.get('/api/notes/'+n['id']+'/export').text=='new'
    assert c.put('/api/notes/'+n['id'],headers=H,json={**r.json(),'archived':False}).status_code==200
    assert c.post('/api/notes',headers=H,json={'title':'   '}).status_code==422

def seed():
    upsert_papers('molecules',[dict(id=str(i),version=1,title='Paper '+str(i),abstract='Abstract',authors=[],categories=[],published=now(),updated=now()) for i in range(2)])
    with Session.begin() as s:
        a=Analysis(paper_id='0',domain_id='molecules',version=1,taxonomy_version=1,model='fixture',content_hash='lesson-fixture',result={'topics':['性质预测'],'claims':[{'kind':'method','text':'A method','page':1,'quote':'Exact quotation in the paper.'}]});s.add(a);s.flush();aid=a.id
    (DATA/'documents').mkdir(exist_ok=True);(DATA/'documents'/'lesson-fixture.json').write_text(json.dumps([{'page':1,'text':'Exact quotation in the paper.'}]))
    return aid

def test_tree_preserves_pending_and_rejects_stale_classification():
    aid=seed();r=c.get('/api/hierarchy').json();assert r['total']==2 and r['classified']==1
    d=next(d for d in r['domains'] if d['id']=='molecules');assert len(d['pending'])==1
    assert next(t for t in d['topics'] if t['name']=='性质预测')['papers'][0]['id']=='0'
    with Session.begin() as s:s.get(Domain,'molecules').taxonomy_version=2
    assert c.get('/api/hierarchy').json()['classified']==0
    assert 'sections' not in c.get('/api/paper?id=0').json()

def test_lesson_queue_deduplicates_and_rejects_unanchored_explanation():
    aid=seed();path=f'/api/lessons/generate?analysis_id={aid}&claim_index=0'
    assert c.post(path,headers=H).json()==c.post(path,headers=H).json()
    assert c.post(f'/api/lessons/generate?analysis_id={aid}&claim_index=7',headers=H).status_code==404
    class Fake:
        def __init__(self,quote):self.quote=quote
        def generate(self,prompt):
            return dict(title='教学示例',motivation='说明'*50,prerequisites='假设'*30,symbols=[{'symbol':'x','meaning':'变量','domain_units':'实数'}],equations=[{'latex':'x^2','explanation':'平方','origin':'teaching'}],derivation='推导'*100,example='例子'*50,conclusions='结论'*50,limitations='局限'*30,source_ids=[0] if self.quote=='Exact quotation in the paper.' else [999])
    with Session() as s:a=s.get(Analysis,aid)
    assert build_lesson(a,0,Fake('Exact quotation in the paper.'))['equations'][0]['origin']=='teaching'
    with pytest.raises(ValueError):build_lesson(a,0,Fake('This fabricated quotation is absent.'))

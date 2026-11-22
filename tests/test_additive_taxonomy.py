from fastapi.testclient import TestClient
from backend.app import app
from backend.db import Session,Paper,Analysis,Domain
from sqlalchemy import select
from backend.db import Membership

def test_additions_preserve_analysis_but_removals_invalidate():
    with Session.begin() as s:
        d=s.get(Domain,'ml');old=list(d.topics)
        s.add(Paper(id='test-add',title='test',abstract='',published='2020-01-01',updated='2020-01-01'))
        s.add(Analysis(paper_id='test-add',domain_id='ml',version=1,taxonomy_version=d.taxonomy_version,model='test',content_hash='a'*64,result={'topics':[old[0]],'claims':[{'page':1,'quote':'source preserved'}]}))
    c=TestClient(app);payload={'name':'机器学习','query':'cat:cs.LG','topics':old+['新增方向'],'auto_sync':False}
    r=c.put('/api/domains/ml',json=payload,headers={'X-Atlas-Client':'1'});assert r.status_code==200
    with Session() as s:
        rows=list(s.scalars(select(Analysis).where(Analysis.paper_id=='test-add').order_by(Analysis.id)))
        assert len(rows)==2 and rows[-1].taxonomy_version==r.json()['taxonomy_version']
        assert rows[-1].result['claims']==rows[0].result['claims']
    payload['topics']=['新增方向']
    assert c.put('/api/domains/ml',json=payload,headers={'X-Atlas-Client':'1'}).status_code==200
    with Session() as s:assert len(list(s.scalars(select(Analysis).where(Analysis.paper_id=='test-add'))))==2

def test_hierarchy_includes_historical_papers_beyond_recent_200():
    with Session.begin() as s:
        d=s.get(Domain,'ml')
        for i in range(205):
            pid=f'history-{i}'
            s.add(Paper(id=pid,title=pid,abstract='',published=f'{1800+i}-01-01',updated='2020-01-01'))
            s.add(Membership(domain_id='ml',paper_id=pid))
            s.add(Analysis(paper_id=pid,domain_id='ml',version=1,taxonomy_version=d.taxonomy_version,model='test',content_hash='a'*64,result={'topics':[d.topics[0]],'methods':[]}))
    r=TestClient(app).get('/api/hierarchy?days=0&domain_id=ml').json()
    assert r['shown']==r['classified']==r['total']==205
    assert not r['truncated']
    assert 'history-0' in {p['id'] for t in r['domains'][0]['topics'] for p in t['papers']}

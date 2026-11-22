from fastapi.testclient import TestClient
from backend.app import app
from backend.db import Session,Job
client=TestClient(app)
def test_active_jobs_are_not_hidden_by_recent_history():
 with Session.begin() as s:
  s.add(Job(id='active-old',kind='explore',status='running',created='1991-01-01',payload={}))
  for i in range(70):s.add(Job(id=f'done-{i}',kind='explore',status='done',payload={}))
 rows=client.get('/api/jobs').json()
 assert rows[0]['id']=='active-old';assert len(rows)==61
def test_domain_scope_single_multi_and_batch_retry():
 with Session.begin() as s:
  for id,payload in [('one',{'domain_id':'life'}),('multi',{'domain_ids':['life','molecules']}),('other',{'domain_id':'ml'}),('global',{})]:s.add(Job(id=id,kind='trends',payload=payload,status='failed'))
 assert {j['id'] for j in client.get('/api/jobs?domain_id=life').json()}=={'one','multi'}
 r=client.post('/api/jobs/retry-all?domain_id=life',headers={'X-Atlas-Client':'1'});assert r.json()['retried']==2
 with Session() as s:assert s.get(Job,'other').status=='failed';assert s.get(Job,'global').status=='failed'

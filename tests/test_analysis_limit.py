from fastapi.testclient import TestClient
from backend.app import app
from backend.db import Session,Job
client=TestClient(app)
def test_increasing_limit_wakes_budget_only():
 with Session.begin() as s:
  s.add(Job(id='budget',kind='explore',status='waiting',payload={},result={'stage':'awaiting_budget','resume_after':'2999-01-01'}))
  s.add(Job(id='pdf',kind='analyze',status='waiting',payload={},message='等待每日额度恢复',result={'resume_after':'2999-01-01'}))
  s.add(Job(id='network',kind='explore',status='waiting',payload={},result={'stage':'search','resume_after':'2999-01-01'}))
 r=client.put('/api/settings',headers={'X-Atlas-Client':'1'},json={'model':'deepseek-flash','daily_limit':50,'auto_analyze':False});assert r.status_code==200
 with Session() as s:
  assert s.get(Job,'budget').result['resume_after']<'2999'
  assert s.get(Job,'pdf').result['resume_after']<'2999'
  assert s.get(Job,'network').result['resume_after']=='2999-01-01'
 assert client.put('/api/settings',headers={'X-Atlas-Client':'1'},json={'model':'test','daily_limit':0}).status_code==422


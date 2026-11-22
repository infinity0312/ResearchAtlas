from fastapi.testclient import TestClient
from backend.app import app
from backend.db import Session,Job
client=TestClient(app)
def test_batch_retry_preserves_checkpoints_and_does_not_duplicate(monkeypatch):
 monkeypatch.setattr('backend.app.get_key',lambda:'test')
 with Session.begin() as s:
  for id,status,kind,payload,result,msg in [
   ('failed','failed','trends',{'q':'one'},{'coverage':[1]},'error'),
   ('duplicate','failed','trends',{'q':'one'},{},'error'),
   ('network','waiting','explore',{'q':'two'},{'resume_after':'2999'},'arXiv 暂时不可用'),
   ('budget','waiting','explore',{'q':'three'},{'stage':'awaiting_budget'},'额度'),
   ('active','running','analyze',{}, {},'分析中'),
   ('cancelled','failed','explore',{}, {'cancel_requested':True},'已取消')]:
   s.add(Job(id=id,status=status,kind=kind,payload=payload,result=result,message=msg,progress=45))
 r=client.post('/api/jobs/retry-all',headers={'X-Atlas-Client':'1'});assert r.status_code==202;assert r.json()['retried']==2
 with Session() as s:
  assert s.get(Job,'failed').result=={'coverage':[1]};assert s.get(Job,'failed').progress==45
  assert s.get(Job,'network').status=='queued';assert s.get(Job,'budget').status=='waiting';assert s.get(Job,'active').status=='running';assert s.get(Job,'cancelled').status=='failed'
 assert client.post('/api/jobs/retry-all',headers={'X-Atlas-Client':'1'}).json()['retried']==0

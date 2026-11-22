from fastapi.testclient import TestClient
from backend.app import app
from backend.db import Session,Job
from backend.task_control import check_pause,TaskPaused
import pytest
c=TestClient(app);H={'X-Atlas-Client':'1'}
def test_pause_resume_retains_checkpoint_and_budget_wait():
 with Session.begin() as s:
  s.add(Job(id='run',kind='explore',payload={},status='running',progress=45,result={'coverage':[1]}))
  s.add(Job(id='budget',kind='analyze',payload={},status='waiting',result={'resume_after':'2999'}))
 assert c.post('/api/jobs/run/pause',headers=H).status_code==200
 with pytest.raises(TaskPaused):check_pause('run')
 with Session.begin() as s:
  j=s.get(Job,'run');assert j.progress==45 and j.result['coverage']==[1];j.status='paused'
 assert c.post('/api/jobs/run/resume',headers=H).status_code==200
 check_pause('run')
 c.post('/api/jobs/budget/pause',headers=H);c.post('/api/jobs/budget/resume',headers=H)
 with Session() as s:assert s.get(Job,'budget').status=='waiting';assert s.get(Job,'budget').result['resume_after']=='2999'
def test_folder_paths_persist_and_colors_are_unique():
 assert c.post('/api/note-folders',headers=H,json={'path':'Research / Molecules'}).status_code==200
 assert 'Research/Molecules' in c.get('/api/note-folders').json()
 assert c.post('/api/note-folders',headers=H,json={'path':'../bad'}).status_code==422
 n=c.post('/api/notes',headers=H,json={'title':'test','series':'Research/Molecules'}).json()
 assert c.request('DELETE','/api/note-folders',headers=H,json={'path':'Research/Molecules'}).status_code==409
 rows=c.get('/api/trends/series').json();assert len({r['color'] for r in rows})==len(rows)
def test_bulk_pause_preserves_manual_pause_and_waiting_schedule():
 with Session.begin() as s:
  s.add(Job(id='q',kind='explore',payload={},status='queued',result={'coverage':[1]}))
  s.add(Job(id='w',kind='analyze',payload={},status='waiting',result={'resume_after':'2999'}))
  s.add(Job(id='manual',kind='explore',payload={},status='paused'))
 assert c.post('/api/jobs/pause-all',headers=H).json()['affected']==2
 assert c.get('/api/jobs/control').json()['paused']
 assert c.post('/api/jobs/pause-all',headers=H).json()['affected']==0
 assert c.post('/api/jobs/resume-all',headers=H).json()['affected']==2
 with Session() as s:
  assert s.get(Job,'q').status=='queued';assert s.get(Job,'q').result['coverage']==[1]
  assert s.get(Job,'w').status=='waiting';assert s.get(Job,'w').result['resume_after']=='2999'
  assert s.get(Job,'manual').status=='paused'

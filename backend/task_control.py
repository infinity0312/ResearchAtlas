"""Cooperative pause at persisted task checkpoints."""
from fastapi import APIRouter,HTTPException
from .db import Session,Job,Setting
from sqlalchemy import select
from pydantic import BaseModel,Field
router=APIRouter(prefix='/api/jobs')
class SelectedJobs(BaseModel):
 ids:list[str]=Field(min_length=1,max_length=100)

@router.post('/run-statistics-only')
def run_statistics_only(data:SelectedJobs):
 """Explicitly run only the selected no-model statistics jobs; keep old work paused."""
 with Session.begin() as s:
  s.connection().exec_driver_sql('BEGIN IMMEDIATE')
  rows=[s.get(Job,id) for id in set(data.ids)]
  if any(not j or j.kind!='trends' or j.payload.get('quality') or j.status not in ('queued','paused') or j.result.get('cancel_requested') or s.get(Setting,'job-hidden:'+j.id) for j in rows):raise HTTPException(409,'只允许未执行的纯统计任务')
  for j in rows:
   j.status='queued';j.result={k:v for k,v in j.result.items() if k not in ('pause_requested','resume_status','bulk_paused')}
  gate=s.get(Setting,'background_control')
  previous=gate.value.get('allowed_ids',[]) if gate and gate.value.get('manual_only') else []
  s.merge(Setting(key='background_control',value={'paused':False,'manual_only':True,'allowed_ids':list(dict.fromkeys(previous+data.ids))}))
 return {'started':len(rows),'model_calls':False}
class TaskPaused(Exception):pass
def check_pause(jid):
 with Session() as s:
  j=s.get(Job,jid)
  gate=s.get(Setting,'background_control')
  explicit=bool(j and j.payload.get('intake_scope') and j.result.get('intake_explicit'))
  if j and (j.result.get('pause_requested') or j.result.get('cancel_requested') or j.result.get('hidden') or (gate and gate.value.get('paused') and not explicit)):raise TaskPaused('已暂停，已完成的阶段和缓存已保留')
@router.post('/{jid}/pause')
def pause(jid:str):
 with Session.begin() as s:
  j=s.get(Job,jid)
  if not j:raise HTTPException(404,'任务不存在')
  if j.status not in ('queued','running','waiting'):raise HTTPException(409,'此任务当前无法暂停')
  j.result={**j.result,'pause_requested':True,'resume_status':j.status}
  if j.status!='running':j.status='paused';j.message='已暂停，进度已保存'
  else:j.message='正在暂停：完成当前请求并保存进度后停止'
 return {'ok':True}
@router.post('/{jid}/resume')
def resume(jid:str):
 with Session.begin() as s:
  j=s.get(Job,jid)
  if not j or j.status!='paused':raise HTTPException(409,'只能继续已暂停任务')
  if j.result.get('cancel_requested') or s.get(Setting,'job-hidden:'+jid):raise HTTPException(409,'任务已取消或删除')
  j.status='waiting' if j.result.get('resume_status')=='waiting' else 'queued'
  j.result={k:v for k,v in j.result.items() if k not in ('pause_requested','resume_status')};j.message='已恢复，等待续传';j.finished=None
 return {'ok':True}

@router.get('/control')
def control():
 with Session() as s:
  gate=s.get(Setting,'background_control');return {'paused':bool(gate and gate.value.get('paused'))}
@router.post('/pause-all')
def pause_all():
 count=0
 with Session.begin() as s:
  s.connection().exec_driver_sql('BEGIN IMMEDIATE')
  s.merge(Setting(key='background_control',value={'paused':True}))
  for j in s.scalars(select(Job).where(Job.status.in_(['queued','running','waiting']))):
   if j.result.get('pause_requested') and j.status=='running':continue
   j.result={**j.result,'pause_requested':True,'resume_status':j.status,'bulk_paused':True}
   if j.status!='running':j.status='paused';j.message='全部任务已暂停，进度已保存'
   else:j.message='正在暂停：完成当前请求后保存进度'
   count+=1
 return {'paused':True,'affected':count}
@router.post('/resume-all')
def resume_all():
 count=0
 with Session.begin() as s:
  s.connection().exec_driver_sql('BEGIN IMMEDIATE')
  s.merge(Setting(key='background_control',value={'paused':False}))
  for j in s.scalars(select(Job).where(Job.status.in_(['paused','running']))):
   if j.result.get('cancel_requested') or s.get(Setting,'job-hidden:'+j.id):continue
   if not j.result.get('bulk_paused'):continue
   if j.status=='paused':j.status='waiting' if j.result.get('resume_status')=='waiting' else 'queued';j.message='已恢复，等待续传'
   j.result={k:v for k,v in j.result.items() if k not in ('pause_requested','resume_status','bulk_paused')};count+=1
 return {'paused':False,'affected':count}

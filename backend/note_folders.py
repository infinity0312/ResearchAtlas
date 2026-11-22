from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select
from .db import Session,Setting,Note,now
router=APIRouter(prefix='/api/note-folders')
class FolderInput(BaseModel):
 path:str=Field(min_length=1,max_length=100)
 @field_validator('path')
 @classmethod
 def clean(cls,v):
  parts=[x.strip() for x in v.replace('\\','/').split('/')]
  if any(not x or x in ('.','..') for x in parts):raise ValueError('请使用有效的文件夹名称，子文件夹以 / 分隔')
  if any(any(c in x for c in '<>:"|?*') or x.endswith('.') for x in parts):raise ValueError('文件夹名称含不支持的字符')
  return '/'.join(parts)
def paths(s):
 stored=s.get(Setting,'note_folders');values=set(stored.value.get('paths',[]) if stored else [])
 values.update(s.scalars(select(Note.series)))
 return sorted({ '/'.join(p.split('/')[:i]) for p in values for i in range(1,len(p.split('/'))+1)})
@router.get('')
def folders():
 with Session() as s:return paths(s)
@router.post('')
def create(data:FolderInput):
 with Session.begin() as s:
  s.connection().exec_driver_sql('BEGIN IMMEDIATE');values=set(paths(s))
  if data.path.casefold() in {v.casefold() for v in values}:raise HTTPException(409,'同位置已存在这个文件夹')
  values.add(data.path);s.merge(Setting(key='note_folders',value={'paths':sorted(values)}))
 return {'path':data.path}
@router.delete('')
def delete(data:FolderInput):
 with Session.begin() as s:
  s.connection().exec_driver_sql('BEGIN IMMEDIATE');values=paths(s)
  if any(v.startswith(data.path+'/') for v in values) or s.scalar(select(Note.id).where(Note.series==data.path).limit(1)):raise HTTPException(409,'仅能删除没有笔记及子文件夹的空文件夹')
  s.merge(Setting(key='note_folders',value={'paths':[v for v in values if v!=data.path]}))
 return {'ok':True}

class FolderMove(BaseModel):
 path:str
 destination:str
@router.put('')
def move(data:FolderMove):
 old=FolderInput(path=data.path).path;new=FolderInput(path=data.destination).path
 with Session.begin() as s:
  s.connection().exec_driver_sql('BEGIN IMMEDIATE');values=paths(s)
  if old not in values:raise HTTPException(404,'文件夹不存在')
  if new==old:return {'path':new}
  if new.startswith(old+'/'):raise HTTPException(409,'不能移动到自身子文件夹')
  if new.casefold() in {v.casefold() for v in values}:raise HTTPException(409,'目标文件夹已存在')
  def renamed(v):return new+v[len(old):] if v==old or v.startswith(old+'/') else v
  for n in s.scalars(select(Note)):
   target=renamed(n.series)
   if target!=n.series:n.series=target;n.revision+=1;n.updated=now()
  s.merge(Setting(key='note_folders',value={'paths':sorted({renamed(v) for v in values})}))
 return {'path':new}

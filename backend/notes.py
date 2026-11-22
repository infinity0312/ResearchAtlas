import uuid
from fastapi import APIRouter,HTTPException
from fastapi.responses import Response
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select,update
from .db import Session,Note,Setting,now,serialize
from .note_folders import FolderInput

router=APIRouter(prefix='/api/notes')
@router.get('/trash')
def trash():
    with Session() as s:
        return [r.value for r in s.scalars(select(Setting).where(Setting.key.like('note-trash:%')))]

@router.post('/{nid}/restore')
def restore(nid:str):
    with Session.begin() as s:
        row=s.get(Setting,'note-trash:'+nid)
        if not row:raise HTTPException(404,'回收站中没有这篇笔记')
        if s.get(Note,nid):raise HTTPException(409,'此笔记已恢复')
        data={k:v for k,v in row.value.items() if k!='deleted_at'}
        data['revision']+=1;data['updated']=now()
        n=Note(**data);s.add(n);s.delete(row);s.flush();return serialize(n)

@router.delete('/{nid}')
def delete_note(nid:str,revision:int):
    with Session.begin() as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE')
        n=s.get(Note,nid)
        if not n:raise HTTPException(404,'笔记不存在')
        if n.revision!=revision:raise HTTPException(409,'笔记已被修改，请刷新后删除')
        s.merge(Setting(key='note-trash:'+nid,value={**serialize(n),'deleted_at':now()}));s.delete(n)
    return {'ok':True}
class NoteInput(BaseModel):
    title:str=Field(min_length=1,max_length=160)
    series:str=Field(default='随手记',max_length=100)
    content:str=Field(default='',max_length=200000)
    @field_validator('title','series')
    @classmethod
    def clean(cls,v):
        if not v.strip(): raise ValueError('名称不能为空')
        return v.strip()
    @field_validator('series')
    @classmethod
    def folder_path(cls,v):return FolderInput(path=v).path
class NoteEdit(NoteInput):
    revision:int=Field(ge=1)
    archived:bool=False

@router.get('')
def listing():
    with Session() as s: return [dict(r._mapping) for r in s.execute(select(Note.id,Note.title,Note.series,Note.revision,Note.archived,Note.updated).order_by(Note.updated.desc()))]
@router.get('/{nid}')
def detail(nid:str):
    with Session() as s:
        note=s.get(Note,nid)
        if not note: raise HTTPException(404,'笔记不存在')
        links=s.execute(select(Note.id,Note.title).where(Note.id!=nid,Note.archived==False,(Note.content.contains('[['+note.title+']]',autoescape=True))|(Note.content.contains('[['+note.title+'|',autoescape=True)))).all()
        return dict(serialize(note),backlinks=[dict(r._mapping) for r in links])
@router.post('',status_code=201)
def create(data:NoteInput):
    with Session.begin() as s:
        note=Note(id=uuid.uuid4().hex,**data.model_dump());s.add(note);s.flush();return serialize(note)
@router.put('/{nid}')
def save(nid:str,data:NoteEdit):
    with Session.begin() as s:
        current=s.get(Note,nid)
        if not current: raise HTTPException(404,'笔记不存在')
        if current.revision!=data.revision and all(getattr(current,k)==v for k,v in data.model_dump(exclude={'revision'}).items()):
            return serialize(current)  # A pagehide save may have committed before its response was lost.
        result=s.execute(update(Note).where(Note.id==nid,Note.revision==data.revision).values(**data.model_dump(exclude={'revision'}),revision=data.revision+1,updated=now()))
        if result.rowcount!=1: raise HTTPException(409,'笔记已在另一窗口修改。当前草稿已保留，请重新载入后对照合并。')
        s.expire_all();return serialize(s.get(Note,nid))
@router.get('/{nid}/export')
def export(nid:str):
    with Session() as s:
        note=s.get(Note,nid)
        if not note: raise HTTPException(404,'笔记不存在')
        return Response(note.content,media_type='text/markdown; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="note-{nid}.md"'})

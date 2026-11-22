"""Revision-checked bibliographic corrections, independent of PDF version."""
import hashlib,json,uuid
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .db import Session,Paper,Setting,serialize,now,touch

router=APIRouter(prefix='/api/paper')
def packet(p):
    fields={k:getattr(p,k) for k in ('title','abstract','authors','categories','published','version')}
    return {**fields,'revision':hashlib.sha256(json.dumps(fields,ensure_ascii=False,sort_keys=True).encode()).hexdigest()}

@router.get('/metadata')
def read_metadata(id:str):
    with Session() as s:
        p=s.get(Paper,id)
        if not p:raise HTTPException(404,'论文不存在')
        return packet(p)

class MetadataCorrection(BaseModel):
    revision:str
    abstract:str|None=Field(default=None,max_length=30000)
    authors:list[str]|None=Field(default=None,max_length=500)
    source:str=Field(min_length=8,max_length=2000)
    evidence:str=Field(min_length=12,max_length=4000)

@router.put('/metadata')
def correct_metadata(id:str,data:MetadataCorrection):
    with Session.begin() as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE');p=s.get(Paper,id)
        if not p:raise HTTPException(404,'论文不存在')
        before=packet(p)
        if before['revision']!=data.revision:raise HTTPException(409,'书目信息已变化，请合并最新版本')
        if data.abstract is not None:
            if not data.abstract.strip():raise HTTPException(422,'摘要不能为空')
            p.abstract=data.abstract.strip()
        if data.authors is not None:
            if not data.authors or any(not name.strip() or len(name)>250 for name in data.authors):raise HTTPException(422,'作者列表无效')
            p.authors=list(dict.fromkeys(name.strip() for name in data.authors))
        after=packet(p)
        s.add(Setting(key='metadata-review:'+uuid.uuid4().hex,value={'paper_id':id,'before':before,'after':after,'source':data.source,'evidence':data.evidence,'created':now()}))
        touch(s)
        return after

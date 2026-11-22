import re
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from .db import Session,Paper,GraphLabel
router=APIRouter(prefix='/api')
def acronym(method,title):
    # A named contribution in the title outranks an internal operator or parameter.
    named=re.match(r'^\s*([A-Za-z][A-Za-z0-9-]{1,23})\s*[:：]',title)
    if named and (any(c.isupper() for c in named[1][1:]) or named[1].isupper()):return named[1]
    value=method or title
    explicit=re.search(r'\(([A-Z][A-Za-z0-9-]{2,15})\)',value)
    if explicit:return explicit.group(1)
    known=re.search(r'(?<![A-Za-z])[A-Z][A-Z0-9-]{1,15}(?![A-Za-z])',value)
    if known:return known.group()
    words=re.findall(r'[A-Za-z][A-Za-z0-9]*',value)
    words=[w for w in words if w.lower() not in {'the','a','an','of','for','and','with','to','in','via'}]
    if len(words)==1:return words[0][:16]
    if words:return ''.join(w[0].upper() for w in words)[:12]
    defaults={'交叉注意力融合':'CAF','形态发生图生成框架':'MGG'}
    if value in defaults:return defaults[value]
    return acronym('',title) if method and title else (re.sub(r'[^\w]','',value)[:8] or 'Paper')
class LabelInput(BaseModel):
    label:str=Field(default='',max_length=24)
@router.put('/paper/graph-label')
def save_label(data:LabelInput,id:str):
    label=data.label.strip()
    if any(c.isspace() for c in label):raise HTTPException(422,'简称请使用一个词，不含空格')
    with Session.begin() as s:
        if not s.get(Paper,id):raise HTTPException(404,'论文不存在')
        s.merge(GraphLabel(paper_id=id,label=label))
    return {'label':label}

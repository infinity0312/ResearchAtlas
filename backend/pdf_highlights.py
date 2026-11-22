from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field,model_validator
from sqlalchemy import select
from .db import Session,Paper,PdfHighlight,serialize
router=APIRouter(prefix='/api/paper/highlights')
class Rect(BaseModel):
    x:float=Field(ge=0,le=1,allow_inf_nan=False)
    y:float=Field(ge=0,le=1,allow_inf_nan=False)
    w:float=Field(gt=0,le=1,allow_inf_nan=False)
    h:float=Field(gt=0,le=1,allow_inf_nan=False)
    @model_validator(mode='after')
    def bounds(self):
        if self.x+self.w>1.001 or self.y+self.h>1.001:raise ValueError('标注超出页面')
        return self
class Highlight(BaseModel):
    version:int=Field(ge=1)
    page:int=Field(ge=1,le=10000)
    quote:str=Field(min_length=1,max_length=8000)
    rects:list[Rect]=Field(min_length=1,max_length=300)
    note:str=Field(default='',max_length=4000)
@router.get('')
def listing(id:str,version:int):
    with Session() as s:return [serialize(r) for r in s.scalars(select(PdfHighlight).where(PdfHighlight.paper_id==id,PdfHighlight.version==version).order_by(PdfHighlight.page,PdfHighlight.created))]
@router.post('')
def create(id:str,data:Highlight):
    with Session.begin() as s:
        if not s.get(Paper,id):raise HTTPException(404,'论文不存在')
        row=PdfHighlight(paper_id=id,**data.model_dump());s.add(row);s.flush();return serialize(row)
class Note(BaseModel):
    note:str=Field(max_length=4000)
@router.patch('/{highlight_id}')
def update(highlight_id:str,id:str,data:Note):
    with Session.begin() as s:
        row=s.get(PdfHighlight,highlight_id)
        if not row or row.paper_id!=id:raise HTTPException(404,'标注不存在')
        row.note=data.note;return serialize(row)
@router.delete('/{highlight_id}')
def delete(highlight_id:str,id:str):
    with Session.begin() as s:
        row=s.get(PdfHighlight,highlight_id)
        if not row or row.paper_id!=id:raise HTTPException(404,'标注不存在')
        s.delete(row);return {'deleted':True}

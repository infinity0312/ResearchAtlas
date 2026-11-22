from fastapi import APIRouter
from pydantic import BaseModel
from .db import Session,Setting,now
router=APIRouter(prefix='/api/model-control')
class Control(BaseModel):enabled:bool
@router.get('')
def status():
    with Session() as s:
        row=s.get(Setting,'model_control')
        return row.value if row else {'enabled':True}
@router.post('')
def configure(data:Control):
    value={'enabled':data.enabled,'updated':now()}
    with Session.begin() as s:s.merge(Setting(key='model_control',value=value))
    return value
def require_enabled():
    if not status().get('enabled',True):raise ValueError('DeepSeek 调用已关闭；请使用深度协作，或在设置中明确恢复模型调用')

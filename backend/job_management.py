"""Reversible task cleanup; a running request stops at its next checkpoint."""
import json,uuid
from fastapi import APIRouter,HTTPException
from sqlalchemy import select
from .db import Session,Job,Analysis,Paper,Domain,Setting,now
from .query_identity import payload_identity
router=APIRouter(prefix='/api/jobs')

def cancel_row(j,reason):
    j.result={**j.result,'cancel_requested':True,'pause_requested':True,'cancel_reason':reason}
    if j.status!='running':j.status='cancelled';j.finished=now()
    j.message=reason+('；当前请求结束后停止' if j.status=='running' else '')

@router.post('/{jid}/cancel')
def cancel(jid:str):
    with Session.begin() as s:
        j=s.get(Job,jid)
        if not j:raise HTTPException(404,'任务不存在')
        if j.status not in ('queued','running','waiting','paused'):raise HTTPException(409,'此任务已结束')
        cancel_row(j,'已取消任务，保留已有结果和缓存')
    return {'ok':True}

@router.delete('/{jid}')
def remove(jid:str):
    with Session.begin() as s:
        j=s.get(Job,jid)
        if not j:raise HTTPException(404,'任务不存在')
        if j.status in ('queued','running','waiting','paused'):cancel_row(j,'删除任务：停止后续执行，保留已有数据')
        j.result={**j.result,'hidden':True,'deleted_at':now()}
        s.merge(Setting(key='job-hidden:'+jid,value={'deleted_at':now()}))
    return {'ok':True}

@router.post('/manage')
def manage():
    counts={'duplicates_cancelled':0,'completed_cancelled':0,'retry_ready':0,'preserved':0,'escalated':0}
    with Session.begin() as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE')
        jobs=list(s.scalars(select(Job).order_by(Job.created)))
        # Prefer the existing running owner, then the oldest unfinished record.
        jobs.sort(key=lambda j:0 if j.status=='running' else 1)
        seen=set()
        for j in jobs:
            if j.result.get('cancel_requested'):
                if j.status!='running':j.status='cancelled'
                continue
            if j.result.get('hidden') or j.status not in ('running','queued','waiting','paused','failed'):continue
            identity=json.dumps([j.kind,payload_identity(j.payload)],sort_keys=True,ensure_ascii=False)
            if identity in seen:
                cancel_row(j,'已取消重复任务，保留另一项执行记录');counts['duplicates_cancelled']+=1;continue
            seen.add(identity)
            if j.kind=='lesson' and j.status=='failed':
                # Repeated mathematical/semantic failures need deliberate review, not blind retries.
                a=s.get(Analysis,j.payload.get('analysis_id'))
                if a:
                    from .collaboration import snapshot,PREFIX
                    ref=f'analysis:{a.id}/method:{j.payload.get("claim_index")}'
                    existing=next((r for r in s.scalars(select(Setting).where(Setting.key.like(PREFIX+'%'))) if ref in r.value.get('instruction','') and r.value['status']!='cancelled'),None)
                    if not existing:
                        _,base=snapshot(s,[a.paper_id]);wid=uuid.uuid4().hex
                        s.add(Setting(key=PREFIX+wid,value={'id':wid,'title':'核查数学讲解 · '+a.paper_id,'instruction':ref+'\n原任务未通过验证：'+j.message+'\n请阅读原文与附录，核对符号、公式与推导，区分论文结论和教学补充。','paper_ids':[a.paper_id],'kind':'derivation','status':'open','revision':1,'base':base,'markdown':'','created':now(),'updated':now()}));s.flush()
                    cancel_row(j,'已转交深度协作，停止自动重复生成数学讲解');counts['escalated']+=1;continue
            if j.kind=='analyze' and j.status!='running':
                p=s.get(Paper,j.payload.get('paper_id'))
                d=s.get(Domain,j.payload.get('domain_id'))
                from .analysis import PROMPT_VERSION
                a=s.scalar(select(Analysis).where(Analysis.paper_id==j.payload.get('paper_id'),Analysis.domain_id==j.payload.get('domain_id'),Analysis.version==(p.version if p else -1),Analysis.taxonomy_version==(d.taxonomy_version if d else -1),Analysis.result['prompt_version'].as_string()==PROMPT_VERSION))
                if a:
                    cancel_row(j,'已有当前论文版本的分析，取消重复计算');counts['completed_cancelled']+=1;continue
            if j.status=='failed':counts['retry_ready']+=1
            else:counts['preserved']+=1
    return counts

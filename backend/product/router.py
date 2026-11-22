"""HTTP adapter for the local product bounded context."""
from contextlib import contextmanager
from typing import Literal
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from ..db import Session, Paper, Analysis, Domain, serialize
from ..analysis_repository import current_query
from .models import ResearchProject, ProjectEvidence, ProjectDelivery, ProjectValidation
from .contracts import ProjectCreate, ProjectEdit, EvidenceInput, ReviewInput, DeliveryInput, ValidationCreate, ValidationEdit, CandidateCreate, CandidateEdit, TrendLeadCreate, TrendLeadEdit, PaperIntakeCreate, PaperIntakeAction, SCENARIOS
from . import service, research_flow, trend_leads, paper_intakes

router=APIRouter(prefix='/api/projects',tags=['研发项目'])


@contextmanager
def write():
    with Session.begin() as s:
        # One lock covers revision check, source/review gates and resulting event.
        s.connection().exec_driver_sql('BEGIN IMMEDIATE')
        yield s


@router.get('/catalog')
def catalog():
    return dict(version='0.3.1',deployment=dict(mode='local',authenticated_identity=False,
        tenant_isolation=False,fulltext_export=False),scenarios=SCENARIOS)


@router.get('/library')
def library(q:str=Query('',max_length=160)):
    with Session() as s:
        query=current_query().where(Analysis.version==Paper.version,Analysis.taxonomy_version==Domain.taxonomy_version)
        if q.strip():
            needle=q.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
            query=query.where(Paper.title.ilike('%'+needle+'%',escape='\\') | Paper.id.ilike('%'+needle+'%',escape='\\'))
        items=[];seen=set()
        for a in s.scalars(query.limit(300)):
            key=(a.paper_id,a.domain_id)
            if key in seen:continue
            seen.add(key)
            view=service.analysis_view(s,a)
            if not view:continue
            paper=s.get(Paper,a.paper_id)
            claims=[dict(index=i,text=c.get('text',''),kind=c.get('kind',''),page=c.get('page',0),quote=c.get('quote',''))
                    for i,c in enumerate((a.result or {}).get('claims',[])) if isinstance(c,dict)]
            if not claims:continue
            items.append(dict(analysis_id=a.id,paper_id=a.paper_id,title=paper.title,
                              domain_id=a.domain_id,quality=view['quality'],claims=claims))
            if len(items)>=12:break
        return dict(items=items)


@router.get('')
def projects():
    with Session() as s:
        items=[]
        for p in s.scalars(select(ResearchProject).order_by(ResearchProject.updated.desc(),ResearchProject.id.desc())):
            d=service.detail(s,p)
            items.append({**d['project'],'readiness':d['readiness'],
                          'evidence_count':len(d['evidence']),'delivery_count':len(d['deliveries'])})
        return dict(items=items,total=len(items))


@router.post('')
def create(data:ProjectCreate):
    with write() as s:
        p=ResearchProject(**data.model_dump())
        s.add(p);s.flush();service.event(s,p,'project_created',dict(scenario=p.scenario))
        return serialize(p)


@router.get('/paper-links')
def paper_links(paper_id: str = Query(min_length=1, max_length=200)):
    with Session() as s:
        return research_flow.paper_links(s, paper_id)


@router.get('/trend-preview')
def trend_preview(series_id: str = Query(min_length=1, max_length=200),
                  start: str = Query(min_length=4, max_length=7),
                  end: str = Query(min_length=4, max_length=7),
                  interval: Literal['year', 'month'] = 'year',
                  period: str | None = Query(default=None, max_length=7),
                  paper_id: str | None = Query(default=None, min_length=1, max_length=200)):
    with Session() as s:
        return trend_leads.preview(s, series_id, start, end, interval, period, paper_id)


@router.get('/{pid}/trend-leads')
def project_trend_leads(pid: str):
    with Session() as s:
        return trend_leads.listing(s, service.project(s, pid))


@router.get('/{pid}/trend-leads/{lid}/intakes')
def paper_intake_list(pid: str, lid: str):
    with Session() as s:
        return paper_intakes.listing(s, pid, lid)


@router.post('/{pid}/trend-leads/{lid}/intakes')
def paper_intake_create(pid: str, lid: str, data: PaperIntakeCreate):
    with write() as s:
        return paper_intakes.create(s, pid, lid, data)


@router.post('/{pid}/trend-leads/{lid}/intakes/{iid}/retry')
def paper_intake_retry(pid: str, lid: str, iid: str, data: PaperIntakeAction):
    with write() as s:
        return paper_intakes.retry(s, pid, lid, iid, data.revision)


@router.post('/{pid}/trend-leads/{lid}/intakes/{iid}/analysis')
def paper_intake_analysis(pid: str, lid: str, iid: str, data: PaperIntakeAction):
    with write() as s:
        return paper_intakes.request_analysis(s, pid, lid, iid, data.revision)


@router.post('/{pid}/trend-leads')
def add_trend_lead(pid: str, data: TrendLeadCreate):
    with write() as s:
        return trend_leads.create(s, service.project(s, pid), data)


@router.put('/{pid}/trend-leads/{lid}')
def edit_trend_lead(pid: str, lid: str, data: TrendLeadEdit):
    with write() as s:
        return trend_leads.edit(s, service.project(s, pid), lid, data)


@router.get('/impacts')
def impacts():
    with Session() as s:
        return research_flow.impacts(s)


@router.get('/{pid}/candidates')
def candidates(pid: str):
    with Session() as s:
        return research_flow.candidates(s, service.project(s, pid))


@router.post('/{pid}/candidates')
def add_candidate(pid: str, data: CandidateCreate):
    with write() as s:
        return research_flow.add_candidate(s, service.project(s, pid), data)


@router.put('/{pid}/candidates/{cid}')
def edit_candidate(pid: str, cid: str, data: CandidateEdit):
    with write() as s:
        return research_flow.edit_candidate(s, service.project(s, pid), cid, data)


@router.get('/{pid}')
def project_detail(pid:str):
    with Session() as s:return service.detail(s,service.project(s,pid))


@router.put('/{pid}')
def edit(pid:str,data:ProjectEdit):
    with write() as s:
        p=service.project(s,pid,data.revision)
        if data.scenario is not None and data.scenario!=p.scenario:
            raise HTTPException(422,'项目场景创建后不能修改')
        ids={c.id for c in data.criteria}
        used=set(s.scalars(select(ProjectEvidence.criterion_id).where(ProjectEvidence.project_id==pid)))
        used.update(s.scalars(select(ProjectValidation.criterion_id).where(ProjectValidation.project_id==pid)))
        if not used<=ids:raise HTTPException(422,'请先移除相关证据，再删除评价标准')
        fields=data.model_dump(exclude={'revision','scenario'})
        if any(getattr(p,k)!=v for k,v in fields.items()):
            before={k:getattr(p,k) for k in fields}
            for k,v in fields.items():setattr(p,k,v)
            service.changed(s,p,'decision_updated',dict(before=before,after=fields))
        return serialize(p)


@router.post('/{pid}/evidence')
def add_evidence(pid:str,data:EvidenceInput):
    with write() as s:return service.attach(s,service.project(s,pid,data.revision),data)


@router.delete('/{pid}/evidence/{eid}')
def remove_evidence(pid:str,eid:str,revision:int=Query(ge=1)):
    with write() as s:
        p=service.project(s,pid,revision);e=s.get(ProjectEvidence,eid)
        if e is None or e.project_id!=pid:raise HTTPException(404,'项目证据不存在')
        snapshot=serialize(e)
        s.delete(e);s.flush();service.changed(s,p,'evidence_removed',dict(evidence_id=eid,before=snapshot))
        return dict(ok=True,revision=p.revision)


@router.put('/{pid}/evidence/{eid}')
def replace_evidence(pid:str,eid:str,data:EvidenceInput):
    with write() as s:
        p=service.project(s,pid,data.revision);e=s.get(ProjectEvidence,eid)
        if e is None or e.project_id!=pid:raise HTTPException(404,'项目证据不存在')
        return service.replace_evidence(s,p,e,data)


@router.post('/{pid}/review')
def review(pid:str,data:ReviewInput):
    with write() as s:return service.review(s,service.project(s,pid,data.revision),data)


@router.post('/{pid}/validations')
def add_validation(pid:str,data:ValidationCreate):
    with write() as s:
        p=service.project(s,pid,data.revision)
        if data.criterion_id not in {c['id'] for c in p.criteria}:
            raise HTTPException(422,'评价标准不属于当前项目')
        v=ProjectValidation(project_id=pid,**data.model_dump(exclude={'revision'}))
        s.add(v);s.flush();service.changed(s,p,'validation_planned',dict(validation_id=v.id))
        return serialize(v)


@router.put('/{pid}/validations/{vid}')
def edit_validation(pid:str,vid:str,data:ValidationEdit):
    with write() as s:
        p=service.project(s,pid,data.revision);v=s.get(ProjectValidation,vid)
        if v is None or v.project_id!=pid:raise HTTPException(404,'项目验证记录不存在')
        if data.status=='completed' and (data.outcome=='pending' or len(data.observation)<10):
            raise HTTPException(422,'完成验证需明确结果及至少10字的实际观察')
        if data.status=='planned' and data.outcome!='pending':
            raise HTTPException(422,'未完成验证的结果须为待验证')
        fields=data.model_dump(exclude={'revision'})
        if any(getattr(v,k)!=value for k,value in fields.items()):
            before={k:getattr(v,k) for k in fields}
            for k,value in fields.items():setattr(v,k,value)
            v.updated=service.now()
            service.changed(s,p,'validation_result_recorded',dict(validation_id=v.id,before=before,after=fields))
        return serialize(v)


@router.post('/{pid}/deliveries')
def deliver(pid:str,data:DeliveryInput):
    with write() as s:return service.deliver(s,service.project(s,pid,data.revision))


def delivery(s,pid,did):
    service.project(s,pid);d=s.get(ProjectDelivery,did)
    if d is None or d.project_id!=pid:raise HTTPException(404,'交付记录不存在')
    return d


@router.get('/{pid}/deliveries/{did}')
def get_delivery(pid:str,did:str):
    with Session() as s:return serialize(delivery(s,pid,did))


@router.get('/{pid}/deliveries/{did}/export')
def export_delivery(pid:str,did:str,format:Literal['md','json']='md'):
    with Session() as s:
        d=delivery(s,pid,did)
        text=d.markdown if format=='md' else service.canonical(dict(digest=d.digest,manifest=d.manifest))
        return Response(text,media_type='text/markdown' if format=='md' else 'application/json',
            headers={'Content-Disposition':f'attachment; filename="research-decision-{d.sequence}.{format}"',
                     'Cache-Control':'no-store','X-Content-SHA256':d.digest})

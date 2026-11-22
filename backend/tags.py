from .db import now
import unicodedata
from datetime import datetime,timedelta,timezone
from typing import Literal
from fastapi import APIRouter,HTTPException,Query
from pydantic import BaseModel,Field
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError
from .db import Session,Tag,PaperTag,Paper,Membership,Analysis,Domain,serialize,GraphLabel,Setting,PaperRelation

router=APIRouter(prefix='/api')
def normalized(value): return unicodedata.normalize('NFKC',' '.join(value.split())).casefold()
class TagInput(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    kind:Literal['method','problem','topic','custom']='method'
    description:str=Field(default='',max_length=1000)
    archived:bool=False

@router.get('/tags')
def tags(archived:bool=False):
    with Session() as s:
        counts=dict(s.execute(select(PaperTag.tag_id,func.count()).where(PaperTag.removed==False).group_by(PaperTag.tag_id)).all())
        rows=list(s.scalars(select(Tag).where(Tag.archived==archived).order_by(Tag.kind,Tag.name)))
        missing={(t.kind,t.normalized) for t in rows if not t.description}
        suggestions={};seen=set()
        if missing:
            query=select(Analysis).join(Paper,Paper.id==Analysis.paper_id).join(Domain,Domain.id==Analysis.domain_id).where(Analysis.version==Paper.version,Analysis.taxonomy_version==Domain.taxonomy_version).order_by(Analysis.created.desc())
            for a in s.scalars(query):
                pair=(a.paper_id,a.domain_id)
                if pair in seen:continue
                seen.add(pair)
                for field,kind in [('methods','method'),('problems','problem'),('topics','topic')]:
                    for name in a.result.get(field,[]):
                        key=(kind,normalized(name))
                        if key not in missing or key in suggestions:continue
                        claim=next((c for c in a.result.get('claims',[]) if key[1] in normalized(c.get('text',''))),None)
                        if claim:suggestions[key]={'suggestion':claim['text'][:1000],'suggestion_paper':a.paper_id}
        return [dict(serialize(t),count=counts.get(t.id,0),**suggestions.get((t.kind,t.normalized),{})) for t in rows]

@router.post('/tags',status_code=201)
def create(data:TagInput):
    if not normalized(data.name): raise HTTPException(422,'标签名称不能为空')
    try:
        with Session.begin() as s:
            row=Tag(**data.model_dump(),normalized=normalized(data.name));row.name=row.name.strip();s.add(row);s.flush();return serialize(row)
    except IntegrityError: raise HTTPException(409,'同类型标签已存在（可能已归档），请编辑或恢复原标签')

@router.put('/tags/{tid}')
def edit(tid:str,data:TagInput):
    if not normalized(data.name): raise HTTPException(422,'标签名称不能为空')
    try:
        with Session.begin() as s:
            row=s.get(Tag,tid)
            if not row: raise HTTPException(404,'标签不存在')
            if normalized(data.name)!=row.normalized: row.aliases=list(dict.fromkeys([*row.aliases,row.normalized]))
            for k,v in data.model_dump().items(): setattr(row,k,v.strip() if isinstance(v,str) else v)
            row.normalized=normalized(row.name);s.flush();return serialize(row)
    except IntegrityError: raise HTTPException(409,'同类型标签名称已存在')

@router.get('/paper/tags')
def paper_tags(id:str):
    with Session() as s:
        return [dict(serialize(t),source=edge.source) for t,edge in s.execute(select(Tag,PaperTag).join(PaperTag,Tag.id==PaperTag.tag_id).where(PaperTag.paper_id==id,PaperTag.removed==False,Tag.archived==False))]

@router.put('/paper/tags/{tid}')
def attach(tid:str,id:str,removed:bool=False):
    with Session.begin() as s:
        if not s.get(Paper,id) or not s.get(Tag,tid): raise HTTPException(404,'论文或标签不存在')
        edge=s.get(PaperTag,(id,tid))
        if not edge: edge=PaperTag(paper_id=id,tag_id=tid);s.add(edge)
        edge.removed=removed;edge.source='manual'
    return {'ok':True}

def import_result(s,paper_id,result):
    if s.get(Setting,'compact-taxonomy'):
        from .taxonomy_curation import compact_result
        result=compact_result(s,result)
    for field,kind in [('methods','method'),('problems','problem'),('topics','topic')]:
        for name in result.get(field,[])[:20]:
            name=name.strip()[:100]
            if not name: continue
            tag=s.scalar(select(Tag).where(Tag.kind==kind,Tag.normalized==normalized(name)))
            if not tag: tag=next((t for t in s.scalars(select(Tag).where(Tag.kind==kind)) if normalized(name) in t.aliases),None)
            if not tag: tag=Tag(name=name,normalized=normalized(name),kind=kind);s.add(tag);s.flush()
            if not tag.archived and not s.get(PaperTag,(paper_id,tag.id)):
                s.add(PaperTag(paper_id=paper_id,tag_id=tag.id,source='analysis'));s.flush()

def reconcile_paper(s,paper_id):
    """Remove stale automatic links, preserving manual tags and explicit removals."""
    s.flush();seen=set();keep=set()
    query=select(Analysis).join(Paper,Paper.id==Analysis.paper_id).join(Domain,Domain.id==Analysis.domain_id).where(Analysis.paper_id==paper_id,Analysis.version==Paper.version,Analysis.taxonomy_version==Domain.taxonomy_version).order_by(Analysis.created.desc(),Analysis.id.desc())
    for a in s.scalars(query):
        if a.domain_id in seen:continue
        seen.add(a.domain_id);result=a.result
        if s.get(Setting,'compact-taxonomy'):
            from .taxonomy_curation import compact_result
            result=compact_result(s,result)
        import_result(s,paper_id,a.result)
        for field,kind in [('methods','method'),('topics','topic'),('problems','problem')]:
            keep.update((kind,normalized(name)) for name in result.get(field,[]))
    retired=[]
    for link in s.scalars(select(PaperTag).where(PaperTag.paper_id==paper_id,PaperTag.source=='analysis',PaperTag.removed==False)):
        tag=s.get(Tag,link.tag_id)
        if (tag.kind,tag.normalized) not in keep and not any((tag.kind,alias) in keep for alias in tag.aliases):
            retired.append(serialize(link));s.delete(link)
    if retired:s.add(Setting(key='tag-link-reconcile:'+paper_id+':'+now(),value={'retired':retired}))

@router.post('/tags/import-analysis')
def import_analysis():
    with Session.begin() as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE')
        seen=set()
        query=select(Analysis).join(Paper,Paper.id==Analysis.paper_id).join(Domain,Domain.id==Analysis.domain_id).where(Analysis.version==Paper.version,Analysis.taxonomy_version==Domain.taxonomy_version).order_by(Analysis.created.desc())
        for a in s.scalars(query):
            key=(a.paper_id,a.domain_id)
            if key in seen: continue
            seen.add(key);import_result(s,a.paper_id,a.result)
    return {'papers':len(seen)}

@router.get('/graph')
def graph(all_tags:bool=False,excluded_ids:list[str]=Query(default=[],max_length=2000),tag_ids:list[str]=Query(default=[]),domain_ids:list[str]=Query(default=[],max_length=100),domain_id:str|None=None,match:Literal['any','all']='any',limit:int=Query(150,ge=1,le=300),days:int=Query(0,ge=0,le=365)):
    if len(tag_ids)>100: raise HTTPException(422,'最多选择 100 个标签')
    if not tag_ids and not all_tags: return {'papers':[],'tags':[],'links':[],'total':0,'truncated':False}
    with Session() as s:
        valid=list(s.scalars(select(Tag).where(Tag.archived==False,Tag.id.not_in(excluded_ids)) if all_tags else select(Tag).where(Tag.id.in_(tag_ids),Tag.archived==False)))
        ids=[t.id for t in valid]
        if not all_tags and match=='all' and len(ids)!=len(set(tag_ids)): return {'papers':[],'tags':[],'links':[],'total':0,'truncated':False}
        selected=select(PaperTag.paper_id).where(PaperTag.tag_id.in_(ids),PaperTag.removed==False).group_by(PaperTag.paper_id)
        if match=='all': selected=selected.having(func.count()==len(ids))
        q=select(Paper) if all_tags and not excluded_ids and s.get(Setting,'compact-taxonomy') else select(Paper).where(Paper.id.in_(selected))
        if days: q=q.where(Paper.published>=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat())
        scope=domain_ids or ([domain_id] if domain_id else [])
        if scope:q=q.where(Paper.id.in_(select(Membership.paper_id).where(Membership.domain_id.in_(scope))))
        total=s.scalar(select(func.count()).select_from(q.subquery()))
        papers=list(s.scalars(q.order_by(Paper.published.desc(),Paper.id).limit(limit)))
        links=[{'paper_id':e.paper_id,'tag_id':e.tag_id,'source':e.source} for e in s.scalars(select(PaperTag).where(PaperTag.paper_id.in_([p.id for p in papers]),PaperTag.tag_id.in_(ids),PaperTag.removed==False))]
        used={e['tag_id'] for e in links}
        from .graph_labels import acronym
        methods={}
        for a in s.scalars(select(Analysis).join(Paper,Paper.id==Analysis.paper_id).join(Domain,Domain.id==Analysis.domain_id).where(Analysis.paper_id.in_([p.id for p in papers]),Analysis.version==Paper.version,Analysis.taxonomy_version==Domain.taxonomy_version).order_by(Analysis.created.desc())):
            if a.paper_id not in methods and a.result.get('methods'):methods[a.paper_id]=a.result['methods'][0]
        overrides={r.paper_id:r.label for r in s.scalars(select(GraphLabel).where(GraphLabel.paper_id.in_([p.id for p in papers])))}
        from .relations import source
        fingerprints={p.id:source(s,p,False)[0] for p in papers}
        relations=[serialize(r) for r in s.scalars(select(PaperRelation).where(PaperRelation.source_id.in_([p.id for p in papers]),PaperRelation.target_id.in_([p.id for p in papers]),PaperRelation.status=='confirmed')) if r.evidence.get('version')==next(p.version for p in papers if p.id==r.source_id) and r.evidence.get('content_hash')==fingerprints.get(r.source_id)]
        return {'relations':relations,'papers':[{'published':p.published,'date_basis':p.date_basis,'id':p.id,'title':p.title,'label':overrides.get(p.id) or acronym(methods.get(p.id,''),p.title),'default_label':acronym(methods.get(p.id,''),p.title),'core_method':methods.get(p.id,''),'custom_label':bool(overrides.get(p.id))} for p in papers],'tags':[serialize(t) for t in valid if t.id in used],'links':links,'total':total,'truncated':total>limit}

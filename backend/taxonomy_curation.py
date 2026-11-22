"""Opt-in compact vocabulary. Original extraction remains immutable in Analysis."""
from fastapi import APIRouter
from sqlalchemy import select
from .db import Session,Setting,Tag,PaperTag,Analysis,Paper,Domain,serialize,now
from .method_families import family
router=APIRouter(prefix='/api/taxonomy')

def compact_result(s,result):
    row=s.get(Setting,'method_families');overrides=row.value if row else {}
    families={family(m,overrides) for m in result.get('methods',[])}-{'待归类','实验指标 / 工具（不计入家族）'}
    topics={t for d in s.scalars(select(Domain)) for t in d.topics}
    return {'methods':sorted(families),'topics':[t for t in result.get('topics',[]) if t in topics]}

def plan(s):
    from .tags import normalized
    canonical=set();seen=set();analyses=[]
    for a in s.scalars(select(Analysis).join(Paper,Paper.id==Analysis.paper_id).join(Domain,Domain.id==Analysis.domain_id).where(Analysis.version==Paper.version,Analysis.taxonomy_version==Domain.taxonomy_version).order_by(Analysis.created.desc())):
        if (a.paper_id,a.domain_id) in seen:continue
        seen.add((a.paper_id,a.domain_id));analyses.append(a)
        r=compact_result(s,a.result)
        for field,kind in [('methods','method'),('topics','topic')]:canonical.update((kind,normalized(v)) for v in r[field])
    manual=set(s.scalars(select(PaperTag.tag_id).where(PaperTag.source=='manual')))
    automatic=set(s.scalars(select(PaperTag.tag_id).where(PaperTag.source=='analysis')))
    retire=[t for t in s.scalars(select(Tag).where(Tag.archived==False)) if t.id in automatic and t.id not in manual and not t.description and not t.aliases and (t.kind,t.normalized) not in canonical]
    return analyses,retire,canonical

@router.get('/plan')
def preview():
    with Session() as s:
        analyses,retire,canonical=plan(s)
        return {'archive_count':len(retire),'canonical_count':len(canonical),'papers':len({a.paper_id for a in analyses}),'enabled':bool(s.get(Setting,'compact-taxonomy'))}

@router.post('/apply')
def apply():
    from .tags import import_result,reconcile_paper
    with Session.begin() as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE')
        analyses,retire,canonical=plan(s)
        s.add(Setting(key='taxonomy-audit:'+now(),value={'archived':[serialize(t) for t in retire],'canonical':sorted(canonical)}))
        s.merge(Setting(key='compact-taxonomy',value={'enabled':True,'updated':now()}));s.flush()
        for t in retire:t.archived=True
        for a in analyses:import_result(s,a.paper_id,a.result)
        for pid in {a.paper_id for a in analyses}:reconcile_paper(s,pid)
        return {'archived':len(retire),'canonical_count':len(canonical),'papers':len({a.paper_id for a in analyses})}

@router.post('/sync-directions')
def sync_all_directions():
    from .topic_catalog import CATALOG,sync_directions
    from .app import edit_domain,DomainInput
    with Session() as s:domains=list(s.scalars(select(Domain)))
    for d in domains:
        topics=list(dict.fromkeys(d.topics+[x['name'] for x in CATALOG if x['domain']==d.name]))
        if topics!=d.topics:edit_domain(d.id,DomainInput(name=d.name,description=d.description,query=d.query,topics=topics,auto_sync=d.auto_sync))
    return sync_directions()

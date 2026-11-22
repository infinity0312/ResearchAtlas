from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,Query
from sqlalchemy import select,func
from .db import Session,Paper,Analysis,Domain,Membership

router=APIRouter(prefix='/api')
@router.get('/hierarchy')
def hierarchy(domain_id:str='',domain_ids:list[str]=Query(default=[],max_length=100),days:int=Query(30,ge=0,le=365)):
    with Session() as s:
        scope=domain_ids or ([domain_id] if domain_id else [])
        domains=list(s.scalars(select(Domain).where(Domain.id.in_(scope)))) if scope else list(s.scalars(select(Domain)))
        q=select(Paper).where(Paper.id.in_(select(Membership.paper_id).where(Membership.domain_id.in_([d.id for d in domains]))))
        if days:q=q.where(Paper.published>=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat())
        total=s.scalar(select(func.count()).select_from(q.subquery()))
        # A taxonomy is an inventory, not a recent-paper feed. Limiting before
        # bucketing silently erased historical branches as the library grew.
        papers=list(s.scalars(q.order_by(Paper.published.desc(),Paper.id)))
        ids=[p.id for p in papers];members=set(s.execute(select(Membership.domain_id,Membership.paper_id).where(Membership.paper_id.in_(ids))).all())
        current={};previous=set();versions={p.id:p.version for p in papers};taxonomy={d.id:d.taxonomy_version for d in domains}
        for a in s.scalars(select(Analysis).where(Analysis.paper_id.in_(ids)).order_by(Analysis.created.desc(),Analysis.id.desc())):
            previous.add((a.domain_id,a.paper_id))
            if a.version==versions[a.paper_id] and a.taxonomy_version==taxonomy.get(a.domain_id):current.setdefault((a.domain_id,a.paper_id),a)
        output=[];classified=set()
        for d in domains:
            buckets={t:[] for t in d.topics};pending=[]
            for p in papers:
                if (d.id,p.id) not in members:continue
                a=current.get((d.id,p.id));topics=[t for t in a.result.get('topics',[]) if t in buckets] if a else []
                node={'id':p.id,'title':p.title,'methods':a.result.get('methods',[]) if a else []}
                if topics:
                    classified.add(p.id)
                    for t in topics:buckets[t].append(node)
                else:
                    status=('领域尚未定义小方向' if not d.topics else '分类未匹配' if a and a.result.get('topics') else '分析未提取分类' if a else '分类版本待更新' if (d.id,p.id) in previous else '待分析全文')
                    hint={'领域尚未定义小方向':'编辑领域，添加小方向或从综述发布分类','分类未匹配':'分析中的方向未包含在当前分类中，请检查领域定义后重新分析','分析未提取分类':'打开论文查看分析结果，补充领域定义后重新分析','分类版本待更新':'论文或领域分类已更新，打开论文重新分析','待分析全文':'打开论文，执行全文分析后自动归类'}[status]
                    pending.append(dict(node,status=status,hint=hint))
            output.append({'id':d.id,'name':d.name,'origin':d.taxonomy_origin,'version':d.taxonomy_version,'topics':[{'name':t,'papers':ps} for t,ps in buckets.items()],'pending':pending})
        return {'domains':output,'total':total,'shown':len(papers),'classified':len(classified),'truncated':False}

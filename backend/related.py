"""Local, explainable retrieval. Does not imply citation links or LLM validation."""
import math,re
from collections import Counter,defaultdict
from functools import lru_cache
from fastapi import APIRouter,HTTPException,Query
from sqlalchemy import select
from .db import Session,Paper,PaperTag,Tag,Setting

router=APIRouter(prefix='/api')
STOP=set('the and for with from that this these those using used use can has have are was were been into through between over under our their its not but more new paper work study model models learning machine deep neural based data results method methods show also than which such prediction approach proposed propose'.split())
def terms(text):
    return [t for t in re.findall(r'[a-z][a-z0-9-]{2,}|[\u4e00-\u9fff]{2,}',text.casefold()) if t not in STOP]

@lru_cache(maxsize=2)
def index(revision):
    with Session() as s: rows=list(s.execute(select(Paper.id,Paper.title,Paper.abstract,Paper.published,Paper.categories)))
    raw={p.id:Counter(terms(p.title)*3+terms(p.abstract)) for p in rows}
    df=Counter(t for vector in raw.values() for t in vector)
    inv=defaultdict(list);vectors={}
    for pid,vector in raw.items():
        weighted={t:(1+math.log(n))*math.log(1+len(rows)/(1+df[t])) for t,n in vector.items()}
        norm=math.sqrt(sum(v*v for v in weighted.values())) or 1
        vectors[pid]={t:w/norm for t,w in weighted.items()}
        for term,weight in vectors[pid].items(): inv[term].append((pid,weight))
    return {p.id:dict(id=p.id,title=p.title,published=p.published,categories=p.categories) for p in rows},vectors,inv

@router.get('/paper/related')
def related(id:str,limit:int=Query(6,ge=1,le=12)):
    with Session() as s:
        if not s.get(Paper,id): raise HTTPException(404,'论文不存在')
        revision=s.get(Setting,'revision').value['id']
        own=list(s.scalars(select(Tag).join(PaperTag,Tag.id==PaperTag.tag_id).where(PaperTag.paper_id==id,PaperTag.removed==False,Tag.archived==False)))
        shared=defaultdict(list);names={t.id:t.name for t in own}
        if names:
            for edge in s.scalars(select(PaperTag).where(PaperTag.tag_id.in_(names),PaperTag.removed==False,PaperTag.paper_id!=id)): shared[edge.paper_id].append(names[edge.tag_id])
    rows,vectors,inv=index(revision);source=vectors.get(id,{})
    scores=defaultdict(float);overlap=defaultdict(list)
    for term,weight in source.items():
        for pid,other in inv.get(term,[]):
            if pid!=id: scores[pid]+=weight*other;overlap[pid].append((weight*other,term))
    for pid,names in shared.items(): scores[pid]+=min(.6,len(names)*.2)
    items=[]
    for pid,score in sorted(scores.items(),key=lambda x:(-x[1],x[0])):
        if pid not in rows or score<.08: continue
        keywords=[t for _,t in sorted(overlap[pid],reverse=True)[:3]]
        items.append(dict(rows[pid],shared_tags=shared[pid],keywords=keywords))
        if len(items)>=limit: break
    return {'items':items,'basis':'本地文献库 · 共同标签与标题/摘要关键词匹配；不代表引用关系','total_candidates':len(rows)-1}

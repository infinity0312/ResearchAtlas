"""Evidence-backed directed relations. Bibliography matching never infers inheritance."""
import re,json,hashlib,unicodedata
from typing import Literal
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select
from .db import Session,Paper,Analysis,Setting,PaperRelation,DATA,serialize,now
router=APIRouter(prefix='/api/relations')

def source(s,p,load_pages=True):
    a=s.scalar(select(Analysis).where(Analysis.paper_id==p.id,Analysis.version==p.version).order_by(Analysis.created.desc()))
    if not a:return '',[]
    digest=a.content_hash
    # Source edits are chained by original content hash.
    edit=s.get(Setting,'source-edit:'+digest)
    if edit:digest=edit.value['digest']
    path=DATA/'documents'/f'{digest}.json'
    return digest,json.loads(path.read_text('utf8')) if load_pages and path.exists() else []

def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text).lower() if c.isascii() and c.isalnum())

def reference_hits(pages,targets):
    in_refs=False
    for page in pages:
        text=page['text'];heading=re.search(r'(?im)^\s*(?:\d+[. ]+)?(?:references|bibliography)\s*$',text)
        if heading:in_refs=True;text=text[heading.end():]
        elif in_refs and re.search(r'(?im)^\s*(?:appendix|supplementary material)\b',text):in_refs=False
        if not in_refs:continue
        chars=[];positions=[]
        for i,c in enumerate(text):
            for letter in normalized(c):chars.append(letter);positions.append(i)
        cleaned=''.join(chars)
        for target in targets:
            title=normalized(target.title)
            if len(title)<25 or len(target.title.split())<4:continue
            at=cleaned.find(title)
            if at<0:continue
            lo=positions[at];hi=positions[at+len(title)-1]+1
            yield target,{'page':page['page'],'quote':text[max(0,lo-80):min(len(text),hi+100)],'match':'exact-normalized-title-in-bibliography'}

def current(s,r):
    p=s.get(Paper,r.source_id)
    if not p or p.version!=r.evidence.get('version'):return False
    digest,_=source(s,p,False)
    return digest==r.evidence.get('content_hash')

@router.get('')
def listing():
    with Session() as s:
        names={p.id:p.title for p in s.scalars(select(Paper))}
        return [{**serialize(r),'source_title':names.get(r.source_id,r.source_id),'target_title':names.get(r.target_id,r.target_id),'stale':not current(s,r)} for r in s.scalars(select(PaperRelation).order_by(PaperRelation.created.desc()))]

@router.post('/scan')
def scan():
    candidates=[];coverage=[];missing={}
    with Session() as s:
        papers=list(s.scalars(select(Paper)));ids={p.id for p in papers}
        counts={normalized(p.title):sum(normalized(q.title)==normalized(p.title) for q in papers) for p in papers}
        targets=[p for p in papers if counts[normalized(p.title)]==1]
        for p in papers:
            digest,pages=source(s,p);hits=list(reference_hits(pages,[t for t in targets if t.id!=p.id]))
            coverage.append({'paper_id':p.id,'pages':len(pages),'matched':len(hits)})
            for target,evidence in hits:
                candidates.append((p.id,target.id,{**evidence,'content_hash':digest,'version':p.version,'target_version':target.version}))
            in_refs=False
            for page in pages:
                text=page['text'];heading=re.search(r'(?im)^\s*(?:references|bibliography)\s*$',text)
                if heading:in_refs=True;text=text[heading.end():]
                elif in_refs and re.search(r'(?im)^\s*(?:appendix|supplementary material)\b',text):in_refs=False
                if in_refs:
                    for aid in re.findall(r'(?i)arxiv\s*[:/]\s*(\d{4}\.\d{4,5})',text):
                        if aid not in ids:missing.setdefault(aid,[]).append({'paper_id':p.id,'page':page['page']})
    added=0
    with Session.begin() as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE')
        for pid,tid,evidence in candidates:
            existing=s.scalar(select(PaperRelation).where(PaperRelation.source_id==pid,PaperRelation.target_id==tid,PaperRelation.kind=='cites'))
            if existing:continue # Includes rejected records; scans cannot override review.
            p=s.get(Paper,pid);a=s.scalar(select(Analysis).where(Analysis.paper_id==pid,Analysis.version==p.version).order_by(Analysis.created.desc()))
            edit=s.get(Setting,'source-edit:'+a.content_hash) if a else None
            digest=edit.value['digest'] if edit else a.content_hash if a else ''
            if p.version!=evidence['version'] or digest!=evidence['content_hash']:continue
            s.add(PaperRelation(source_id=pid,target_id=tid,kind='cites',evidence=evidence,origin='bibliography-title-match'));s.flush();added+=1
        result={'added':added,'coverage':coverage,'missing':[{'id':pid,'cited_by':refs} for pid,refs in sorted(missing.items())],'created':now()}
        s.merge(Setting(key='relation-scan',value=result))
    return result

@router.get('/gaps')
def gaps():
    with Session() as s:
        r=s.get(Setting,'relation-scan');return r.value if r else {'coverage':[],'missing':[]}

class RelationInput(BaseModel):
    source_id:str
    target_id:str
    kind:Literal['cites','extends','improves']
    page:int=Field(ge=1)
    quote:str=Field(min_length=12,max_length=3000)
    content_hash:str

@router.post('')
def create(data:RelationInput):
    with Session.begin() as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE')
        p=s.get(Paper,data.source_id);t=s.get(Paper,data.target_id)
        if not p or not t or p.id==t.id:raise HTTPException(422,'请选择两篇不同的本地论文')
        digest,pages=source(s,p)
        if digest!=data.content_hash:raise HTTPException(409,'原文版本已变化，请重新读取')
        if not any(x['page']==data.page and data.quote in x['text'] for x in pages):raise HTTPException(422,'引文与原文页码不匹配')
        if s.scalar(select(PaperRelation).where(PaperRelation.source_id==p.id,PaperRelation.target_id==t.id,PaperRelation.kind==data.kind)):raise HTTPException(409,'关系已存在，请查看或恢复原记录')
        r=PaperRelation(source_id=p.id,target_id=t.id,kind=data.kind,evidence={'page':data.page,'quote':data.quote,'content_hash':digest,'version':p.version,'target_version':t.version},origin='manual-reviewed');s.add(r);s.flush();return serialize(r)

class Review(BaseModel):
    revision:int
    status:Literal['confirmed','rejected']

@router.patch('/{rid}')
def review(rid:str,data:Review):
    with Session.begin() as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE');r=s.get(PaperRelation,rid)
        if not r:raise HTTPException(404,'关系不存在')
        if r.revision!=data.revision:raise HTTPException(409,'关系已被修改，请刷新')
        if data.status=='confirmed' and not current(s,r):raise HTTPException(409,'证据已过期，请重新核查')
        s.add(Setting(key='relation-audit:'+rid+':'+str(r.revision),value=serialize(r)))
        r.status=data.status;r.revision+=1;return serialize(r)

@router.get('/catalog')
def catalog():
    with Session() as s:return [{'id':p.id,'title':p.title,'published':p.published} for p in s.scalars(select(Paper).order_by(Paper.published))]

@router.get('/source')
def source_page(paper_id:str,page:int=1):
    with Session() as s:
        p=s.get(Paper,paper_id)
        if not p:raise HTTPException(404,'论文不存在')
        digest,pages=source(s,p)
        return {'content_hash':digest,'version':p.version,'text':next((x['text'] for x in pages if x['page']==page),''),'pages':len(pages)}

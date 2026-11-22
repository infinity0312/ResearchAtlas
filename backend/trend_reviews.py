"""Source-locked macro review packets for a human or Codex; never calls a model."""
import hashlib,re,json
from datetime import datetime
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select
from .db import Session,TrendSeries,SearchSnapshot,CatalogPaper,TrendEvidence,Setting,now,DATA
from .history import digest
from .query_identity import query_identity
from .trend_signals import Assessment,VERSION,SAMPLE,period_key
from .collaboration import owned,get,public
from .macro_coauthor import EditorialReview,validate_editorial,VERSION as COAUTHOR_VERSION
router=APIRouter(prefix='/api/trends')
REVIEWER='codex-source-review'

def packet(s,series_id,year):
 row=s.get(TrendSeries,series_id)
 if not row:raise HTTPException(404,'研究方向不存在')
 if not 1991<=year<datetime.now().year:raise HTTPException(422,'请选择已经结束的年份')
 lo=f'{year}-01-01';hi=f'{year}-12-31'
 snapshots=s.scalars(select(SearchSnapshot).where(SearchSnapshot.complete==True,SearchSnapshot.start<=lo,SearchSnapshot.end>=hi).order_by(SearchSnapshot.fetched.desc()))
 snapshot=next((x for x in snapshots if query_identity(x.query)==query_identity(row.query)),None)
 if not snapshot:raise HTTPException(409,'此周期的完整宏观索引尚未就绪')
 papers=[]
 for pid in snapshot.paper_ids:
  item=s.get(CatalogPaper,pid)
  if not item:raise HTTPException(409,'索引缺少元数据，需要补取')
  p=item.metadata_json
  if lo<=p['published'][:10]<=hi:papers.append(p)
 sample=sorted(papers,key=lambda p:hashlib.sha256(p['id'].encode()).hexdigest())[:SAMPLE]
 sources=[{'id':p['id'],'title':p['title'],'published':p['published'],'passages':[x.strip() for x in re.split(r'(?<=[.!?])\s+(?=[A-Z])',p['abstract']) if x.strip()]} for p in sample]
 for entry in sources:
  extra=s.get(Setting,'macro-fulltext:'+entry['id'])
  if extra:
   entry['passage_sources']=[{'kind':'abstract','url':'https://arxiv.org/abs/'+entry['id']} for _ in entry['passages']]+extra.value['sources']
   entry['passages']+=extra.value['passages'];entry['fulltext_hash']=extra.value['hash']
 value={'series_id':row.id,'name':row.name,'query':row.query,'year':year,'population':len(papers),'papers':sources,'rubric':VERSION}
 return {**value,'source_hash':digest(value)}

@router.get('/review-packet')
def export(series_id:str,year:int):
 with Session() as s:return packet(s,series_id,year)

class Review(BaseModel):
 work_id:str
 token:str
 revision:int
 series_id:str
 year:int
 source_hash:str
 papers:list[Assessment]=Field(max_length=24)
 pipeline:str|None=None
 editorial_review:EditorialReview|None=None

class PdfPassage(BaseModel):
 page:int=Field(ge=1,le=150)
 text:str=Field(min_length=40,max_length=10000)

class PdfSource(BaseModel):
 series_id:str
 year:int
 paper_id:str
 source_hash:str
 content_hash:str=Field(pattern=r'^[0-9a-f]{64}$')
 passages:list[PdfPassage]=Field(min_length=1,max_length=12)

@router.post('/review-source-pdf')
def enrich_pdf_source(data:PdfSource):
 """Append exact passages from an already downloaded, hash-verified sample PDF."""
 from .analysis import parse_pdf
 with Session() as s:
  original=packet(s,data.series_id,data.year)
  if original['source_hash']!=data.source_hash:raise HTTPException(409,'样本来源已变化，请重新读取')
  if data.paper_id not in {p['id'] for p in original['papers']}:raise HTTPException(422,'论文不在固定样本中')
 stem=hashlib.sha256(data.paper_id.encode()).hexdigest()
 path=DATA/'macro-evidence'/'sources'/(stem+'.pdf')
 metadata=path.with_suffix('.json')
 if not path.is_file() or not metadata.is_file():raise HTTPException(404,'本地宏观样本 PDF 尚未下载')
 if hashlib.sha256(path.read_bytes()).hexdigest()!=data.content_hash:raise HTTPException(409,'PDF 哈希不匹配')
 stored=json.loads(metadata.read_text('utf8'))
 if stored.get('id')!=data.paper_id or stored.get('content_hash')!=data.content_hash:raise HTTPException(409,'PDF 来源索引不匹配')
 url=stored.get('source_url','')
 if not re.fullmatch(r'https://arxiv.org/pdf/'+re.escape(data.paper_id)+r'(?:v\d+)?',url):raise HTTPException(422,'PDF 来源必须是对应的官方论文')
 pages,digest_=parse_pdf(path)
 if digest_!=data.content_hash:raise HTTPException(409,'解析源已修订，请先核查新版本')
 bypage={p['page']:p['text'] for p in pages}
 normalize=lambda t:re.sub(r'\s+',' ',t).strip()
 for p in data.passages:
  if p.page not in bypage or normalize(p.text) not in normalize(bypage[p.page]):raise HTTPException(422,'引文未在指定 PDF 页找到')
 with Session.begin() as s:
  s.connection().exec_driver_sql('BEGIN IMMEDIATE')
  if packet(s,data.series_id,data.year)['source_hash']!=data.source_hash:raise HTTPException(409,'补源期间样本已变化')
  old=s.get(Setting,'macro-fulltext:'+data.paper_id)
  value=dict(old.value) if old else {'passages':[],'sources':[]}
  if old:s.merge(Setting(key='macro-fulltext-history:'+data.paper_id+':'+value['hash'],value=value))
  passages=list(value['passages']);sources=list(value['sources'])
  for p in data.passages:
   if p.text in passages:continue
   passages.append(p.text);sources.append({'kind':'fulltext','url':url+'#page='+str(p.page),'section':'PDF 第 '+str(p.page)+' 页','page':p.page,'content_hash':data.content_hash})
  value={**value,'passages':passages,'sources':sources,'hash':digest([passages,sources]),'retrieved':now()}
  s.merge(Setting(key='macro-fulltext:'+data.paper_id,value=value))
 return {'paper_id':data.paper_id,'passages':len(passages)}

@router.post('/publish-review')
def publish(data:Review):
 with Session.begin() as s:
  s.connection().exec_driver_sql('BEGIN IMMEDIATE');work,v=get(s,data.work_id);owned(v,data)
  if v.get('kind')!='curation':raise HTTPException(422,'请使用文献整理协作任务')
  source=packet(s,data.series_id,data.year)
  if source['source_hash']!=data.source_hash:raise HTTPException(409,'宏观样本已变化，请重新核对')
  if v.get('pipeline') and data.pipeline!=v['pipeline']:raise HTTPException(422,'协作任务不能绕过复核流程')
  if data.pipeline is not None:
   if data.pipeline!=COAUTHOR_VERSION or data.editorial_review is None:raise HTTPException(422,'协作候选必须经 GPT 逐篇复核')
   try:validate_editorial(source,[p.model_dump() for p in data.papers],data.editorial_review)
   except ValueError as exc:raise HTTPException(422,str(exc))
  byid={p['id']:p for p in source['papers']}
  if len(data.papers)!=len(byid) or {p.id for p in data.papers}!=set(byid):raise HTTPException(422,'必须逐条核查固定样本，不能只提交高分论文')
  results=[]
  for p in data.papers:
   if not p.relevant and (not p.exclusion_reason.strip() or p.headroom is not None):raise HTTPException(422,'范围外论文须说明排除依据且不评分创新空间')
   passages=byid[p.id]['passages']
   if not 0<=p.evidence_index<len(passages):raise HTTPException(422,'证据序号不存在')
   if (p.headroom is None)!=(p.headroom_evidence is None):raise HTTPException(422,'空间评分须与证据同时存在')
   if p.headroom_evidence is not None and not 0<=p.headroom_evidence<len(passages):raise HTTPException(422,'瓶颈证据序号不存在')
   results.append({**p.model_dump(),'quote':passages[p.evidence_index],'headroom_quote':passages[p.headroom_evidence] if p.headroom_evidence is not None else None,'title':byid[p.id]['title'],'headroom_source':byid[p.id].get('passage_sources',[])[p.headroom_evidence] if p.headroom_evidence is not None and byid[p.id].get('passage_sources') else None})
  result={'population':source['population'],'sample':len(results),'papers':results,'model':REVIEWER,'rubric':VERSION,'created':now(),'source_hash':source['source_hash'],'provenance':{'work_id':data.work_id,'owner':v.get('owner'),'source':'codex-direct-review'}}
  if data.pipeline:result['provenance'].update(pipeline=data.pipeline,source='deepseek-draft-gpt-review',editorial_review=data.editorial_review.model_dump())
  k=period_key(source['query'],f'{data.year}01010000',f'{data.year}12312359',REVIEWER)
  s.merge(TrendEvidence(key=digest([k,result]),result=result));s.merge(TrendEvidence(key=k,result=result));v.update(status='published',revision=v['revision']+1,updated=now(),trend_review_key=k,lease_until='');v.pop('lease_token',None);work.value=v
  return public(v)

@router.post('/review-source')
def enrich_source(series_id:str,year:int,paper_id:str):
 """Fetch official full-text limitations for the fixed sample; no model call."""
 import httpx
 from bs4 import BeautifulSoup
 with Session() as s:
  source=packet(s,series_id,year)
  if paper_id not in {p['id'] for p in source['papers']}:raise HTTPException(422,'论文不在固定样本中')
  old=s.get(Setting,'macro-fulltext:'+paper_id)
  if old:return {'paper_id':paper_id,'passages':len(old.value['passages']),'cached':True}
 if not re.fullmatch(r'\d{4}\.\d{4,5}',paper_id):raise HTTPException(422,'仅支持 arXiv 标准论文编号')
 url='https://arxiv.org/html/'+paper_id
 try:
  r=httpx.get(url,timeout=30,follow_redirects=True);r.raise_for_status()
 except httpx.HTTPError:raise HTTPException(424,'官方 HTML 全文暂不可用，原始证据保留')
 soup=BeautifulSoup(r.text,'html.parser');passages=[];origins=[]
 for section in soup.select('section'):
  heading=section.find(['h2','h3','h4'],recursive=False)
  if not heading or not any(w in heading.get_text().lower() for w in ('conclusion','limitation','discussion','future work')):continue
  for par in section.select('p'):
   text=par.get_text(' ',strip=True)
   if len(text)<40 or text in passages:continue
   passages.append(text[:10000]);origins.append({'kind':'fulltext','url':url+('#'+section['id'] if section.get('id') else ''),'section':heading.get_text(' ',strip=True)})
 if not passages:raise HTTPException(424,'全文没有可定位的讨论或局限性段落')
 value={'passages':passages,'sources':origins,'hash':hashlib.sha256(r.content).hexdigest(),'retrieved':now()}
 with Session.begin() as s:s.merge(Setting(key='macro-fulltext:'+paper_id,value=value))
 return {'paper_id':paper_id,'passages':len(passages),'cached':False}

class MacroRequest(BaseModel):
 series_id:str
 year:int

@router.post('/coauthor-prepare')
def prepare_coauthor(data:MacroRequest):
 from .macro_coauthor import prepare
 with Session() as s:source=packet(s,data.series_id,data.year)
 try:root,status=prepare(source)
 except FileExistsError:raise HTTPException(409,'相同样本正在创建协作任务')
 return {'checkpoint':root.name,**status}

@router.get('/coauthor-progress')
def coauthor_progress():
 items=[]
 root=DATA/'macro-coauthor'
 for path in root.glob('*/status.json'):
  try:
   value=json.loads(path.read_text('utf8'))
   with Session() as session:
    work=session.get(Setting,'collaboration:'+value.get('work_id',''))
    if work and work.value.get('status')=='published':value['status']='published'
   items.append({k:value.get(k) for k in ('name','year','work_id','status','total','completed','tokens','updated')})
  except (OSError,ValueError):continue
 return {'items':sorted(items,key=lambda v:v.get('updated') or '',reverse=True)}

import hashlib, time, uuid, re
from functools import lru_cache
from threading import RLock
from datetime import datetime,timedelta,timezone
from contextlib import asynccontextmanager
from collections import Counter
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, Query
from typing import Literal
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import mimetypes
# Windows registry MIME mappings may label module workers as plain text.
mimetypes.add_type('text/javascript','.mjs')
mimetypes.add_type('application/wasm','.wasm')
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select,func,or_,exists
from .db import *
from .services import enqueue
from .secrets import get_key,save_key
from .analysis_repository import current_query, read_analysis, source_updates, review_certificates

@asynccontextmanager
async def lifespan(app):
    init_db()
    with Session.begin() as s:
        for row in s.scalars(select(PaperConversation).where(PaperConversation.status=='pending')):
            row.status='failed';row.error='服务已重启，请重新提问。'
    from .product.intake_runtime import start,stop
    start()
    try:
        yield
    finally:
        stop()

app=FastAPI(title='Research Atlas',lifespan=lifespan)
from .model_usage import router as model_usage_router
app.include_router(model_usage_router)
from .coauthor_progress import router as coauthor_progress_router
app.include_router(coauthor_progress_router)
from .relations import router as relations_router
from .taxonomy_curation import router as taxonomy_router
app.include_router(relations_router)
app.include_router(taxonomy_router)
from .trend_reviews import router as trend_reviews_router
app.include_router(trend_reviews_router)
from .model_control import router as model_control_router
app.include_router(model_control_router)
from .library_audit import router as library_audit_router
app.include_router(library_audit_router)
from .collaboration import router as collaboration_router
app.include_router(collaboration_router)
from .workspace import router as workspace_router
app.include_router(workspace_router)
from .job_management import router as job_management_router
app.include_router(job_management_router)
from .task_control import router as task_control_router
app.include_router(task_control_router)
from .note_folders import router as note_folders_router
app.include_router(note_folders_router)
from .tags import router as tag_router
app.include_router(tag_router)
from .related import router as related_router
app.include_router(related_router)
from .notes import router as notes_router
from .lessons import router as lessons_router
from .hierarchy import router as hierarchy_router
app.include_router(notes_router)
app.include_router(lessons_router)
app.include_router(hierarchy_router)
from .graph_labels import router as graph_label_router
from .trends import router as trends_router
app.include_router(graph_label_router)
app.include_router(trends_router)
from .method_families import router as method_router
app.include_router(method_router)
from .exploration import router as exploration_router
app.include_router(exploration_router)
from .paper_chat import router as paper_chat_router
app.include_router(paper_chat_router)
from .pdf_highlights import router as highlight_router
app.include_router(highlight_router)
from .paper_import import router as import_router
app.include_router(import_router)
from .paper_metadata import router as metadata_router
app.include_router(metadata_router)
from .analysis_editing import router as analysis_editing_router
app.include_router(analysis_editing_router)
from .product.router import router as product_router
app.include_router(product_router)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','testserver'])

@app.middleware('http')
async def protect(request:Request,call_next):
    if request.url.path.startswith('/api') and request.method not in ('GET','HEAD','OPTIONS'):
        if request.headers.get('X-Atlas-Client')!='1': return JSONResponse({'detail':'需要本机客户端请求标识'},status_code=403)
        origin=request.headers.get('origin')
        if origin and origin not in (str(request.base_url).rstrip('/'),'http://127.0.0.1:5173','http://localhost:5173'):
            return JSONResponse({'detail':'不允许来自其他站点的写入'},status_code=403)
    response=await call_next(request)
    if request.url.path.startswith('/api') and request.method in ('POST','PUT','PATCH','DELETE') and response.status_code<400:
        with Session.begin() as s: touch(s)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    if request.url.path.startswith('/api/settings'): response.headers['Cache-Control']='no-store'
    return response

class DomainInput(BaseModel):
    name:str=Field(min_length=1,max_length=60)
    description:str=Field(default='',max_length=300)
    query:str=Field(min_length=3,max_length=2000)
    topics:list[str]=Field(default_factory=list,max_length=30)
    auto_sync:bool=True
class SettingsInput(BaseModel):
    model:str=Field(min_length=1,max_length=100)
    api_key:str|None=Field(default=None,max_length=500)
    daily_limit:int=Field(default=20,ge=1,le=500)
    auto_analyze:bool=False
class IngestInput(BaseModel):
    domain_id:str
    days:int=Field(default=30,ge=1,le=365)
class AnalysisInput(BaseModel):
    domain_id:str
class StateInput(BaseModel):
    saved:bool|None=None
    read:bool|None=None

def require_model():
    if not get_key(): raise HTTPException(409,'请先在设置中填写 DeepSeek API Key')
def must_domain(s,did):
    d=s.get(Domain,did)
    if not d: raise HTTPException(404,'研究领域不存在')
    return d

@app.get('/api/health')
def health():
    hb=DATA/'worker.heartbeat'
    return {'app':'Research Atlas','status':'ok','storage':'sqlite' if engine.dialect.name=='sqlite' else engine.dialect.name,'worker':hb.exists() and time.time()-hb.stat().st_mtime<15}

@app.get('/api/architecture')
def architecture():
    from .migrations import migration_status
    from .evidence_contracts import PIPELINE_VERSION,CONTRACT_VERSION
    return {'version':'0.3.1','storage':migration_status(engine),
            'analysis_pipeline':PIPELINE_VERSION,'quality_contract':CONTRACT_VERSION,
            'model_accounting':'persistent-reservations','accounting_timezone':'Asia/Shanghai',
            'deep_study':'experimental-editorial-gate',
            'product_domain':'evidence-linked-research-decisions',
            'deployment':{'mode':'local-single-organization-pilot',
                          'authenticated_identity':False,'tenant_isolation':False}}

@app.get('/api/domains')
def domains():
    with Session() as s:
        counts=dict(s.execute(select(Membership.domain_id,func.count()).group_by(Membership.domain_id)).all())
        return [dict(serialize(d),count=counts.get(d.id,0)) for d in s.scalars(select(Domain))]

@app.post('/api/domains')
def create_domain(data:DomainInput):
    topics=list(dict.fromkeys(t.strip()[:60] for t in data.topics if t.strip()))
    with Session.begin() as s:
        d=Domain(id=uuid.uuid4().hex[:12],**data.model_dump(exclude={'topics'}),topics=topics)
        s.add(d); s.flush()
        s.add(Taxonomy(domain_id=d.id,version=1,topics=topics,source='手动预设'))
        return serialize(d)

@app.put('/api/domains/{did}')
def edit_domain(did:str,data:DomainInput):
    with Session.begin() as s:
        d=must_domain(s,did)
        new_topics=list(dict.fromkeys(t.strip()[:60] for t in data.topics if t.strip()))
        if new_topics!=d.topics:
            old_version=d.taxonomy_version
            # Adding categories preserves previously valid assignments and evidence.
            # Copy only the latest current-paper analysis; leave old records immutable.
            compatible=set(d.topics).issubset(new_topics)
            d.taxonomy_version+=1; d.taxonomy_origin='手动修订'
            d.definitions=[t for t in d.definitions if t['name'] in new_topics]
            s.add(Taxonomy(domain_id=did,version=d.taxonomy_version,topics=new_topics,definitions=d.definitions,source='手动修订'))
            if compatible:
                seen=set()
                for a in s.scalars(select(Analysis).join(Paper,Paper.id==Analysis.paper_id).where(Analysis.domain_id==did,Analysis.taxonomy_version==old_version,Analysis.version==Paper.version).order_by(Analysis.created.desc(),Analysis.id.desc())):
                    if a.paper_id in seen:continue
                    seen.add(a.paper_id)
                    if not set(a.result.get('topics',[])).issubset(new_topics):continue
                    result={**a.result,'taxonomy_migration':{'from_analysis':a.id,'from_version':old_version,'reason':'additive categories; existing assignments and source evidence preserved'}}
                    s.add(Analysis(paper_id=a.paper_id,domain_id=did,version=a.version,taxonomy_version=d.taxonomy_version,model=a.model,content_hash=a.content_hash,result=result))
        for key,value in data.model_dump(exclude={'topics'}).items(): setattr(d,key,value)
        d.topics=new_topics
        return serialize(d)

def paper_query(domain_id=None,q='',saved=False,days=30):
    query=select(Paper)
    if domain_id: query=query.join(Membership,Membership.paper_id==Paper.id).where(Membership.domain_id==domain_id)
    if q:
        from .search import search_filter
        query=search_filter(query,q)
    if saved: query=query.where(Paper.saved==True)
    if days: query=query.where(Paper.published>=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat())
    return query

def filter_analysis_fields(query,domain_id=None,topic=None,method=None):
    """Match both labels on one current analysis with an indexed paper lookup."""
    if not topic and not method:return query
    # Correlating only on version made SQLite rebuild the complete domain's
    # matching-ID list for every paper. EXISTS ties the lookup to this paper's
    # indexed ID, while retaining the same-row version/taxonomy guarantees.
    aquery=select(1).select_from(Analysis).join(Domain,Domain.id==Analysis.domain_id).where(
        Analysis.paper_id==Paper.id,Analysis.version==Paper.version,
        Analysis.taxonomy_version==Domain.taxonomy_version).correlate(Paper)
    for field,value in [('topics',topic),('methods',method)]:
        if value:
            values=func.json_each(Analysis.result[field]).table_valued('value')
            aquery=aquery.where(exists(select(1).select_from(values).where(values.c.value==value)))
    if domain_id:aquery=aquery.where(Analysis.domain_id==domain_id)
    return query.where(exists(aquery))

@app.get('/api/papers')
def papers(domain_id:str|None=None,q:str=Query('',max_length=200),saved:bool=False,days:int=Query(30,ge=0,le=3650),page:int=Query(1,ge=1),size:int=Query(30,ge=1,le=100),category:str|None=None,topic:str|None=None,method:str|None=None,feed:bool=False,cursor:str=Query('',max_length=1000),sort:Literal['research','recent']='research'):
    with Session() as s:
        query=paper_query(domain_id,q,saved,days)
        if category:
            values=func.json_each(Paper.categories).table_valued('value')
            query=query.where(exists(select(1).select_from(values).where(values.c.value==category)))
        query=filter_analysis_fields(query,domain_id,topic,method)
        count=s.scalar(select(func.count()).select_from(query.subquery()))
        from .search import ranked_page, search_terms
        terms = search_terms(q)
        reasons = {}
        if terms and sort == 'research':
            rows, next_cursor, reasons = ranked_page(
                s, query, q, scope=[domain_id, saved, days, category, topic, method],
                page=page, size=size, feed=feed, cursor=cursor,
            )
        else:
            if feed and cursor:
                import base64,json
                try:
                    published,pid=json.loads(base64.urlsafe_b64decode(cursor.encode()))
                    if not isinstance(published,str) or not isinstance(pid,str):raise ValueError()
                except Exception:raise HTTPException(422,'滚动位置无效，请重新搜索')
                query=query.where(or_(Paper.published<published,(Paper.published==published)&(Paper.id>pid)))
            rows=list(s.scalars(query.order_by(Paper.published.desc(),Paper.id).offset(0 if feed else (page-1)*size).limit(size+1 if feed else size)))
            more=feed and len(rows)>size
            rows=rows[:size]
            next_cursor=None
            if more:
                import base64,json
                next_cursor=base64.urlsafe_b64encode(json.dumps([rows[-1].published,rows[-1].id]).encode()).decode()
        ids=[p.id for p in rows]
        aq=current_query(ids,domain_id)
        analyses={}
        for a in s.scalars(aq):
            if a.paper_id not in analyses: analyses[a.paper_id]=a
        result=[]
        domain_rows={d.id:d for d in s.scalars(select(Domain))}
        updates=source_updates(s,ids)
        reviews=review_certificates(s,[a.id for a in analyses.values()])
        for p in rows:
            a=analyses.get(p.id)
            result.append(dict(serialize(p),analysis=read_analysis(a,p,domain_rows.get(a.domain_id),updates,independent_review=reviews.get(a.id)) if a else None, **({'search_rank': reasons[p.id]} if p.id in reasons else {})))
        return {'items':result,'total':count,'page':page,'pages':max(1,(count+size-1)//size),'next_cursor':next_cursor,
                'search_scope': {'source': 'local_library', 'terms': terms, 'operator': 'and',
                                 'sort': sort if terms else 'recent'}}

@app.get('/api/paper')
def detail(id:str,domain_id:str|None=None):
    with Session() as s:
        p=s.get(Paper,id)
        if not p: raise HTTPException(404,'论文不存在')
        a=s.scalar(current_query([id],domain_id).limit(1))
        memberships=list(s.scalars(select(Membership.domain_id).where(Membership.paper_id==id)))
        pdf_version=a.version if a else p.version
        pdf_path=DATA/'documents'/f'{hashlib.sha256(p.id.encode()).hexdigest()}v{pdf_version}.pdf'
        # Parsing is an internal pipeline detail; readers receive curated claims and PDF.
        reviews=review_certificates(s,[a.id]) if a else {}
        return dict(serialize(p),analysis=read_analysis(a,p,s.get(Domain,a.domain_id),source_updates(s,[id]),full=True,independent_review=reviews.get(a.id)) if a else None,domain_ids=memberships,has_pdf=pdf_path.exists(),pdf_version=pdf_version)

@app.get('/api/paper/research-trace')
def paper_research_trace(id: str, version: int = Query(ge=1), analysis_id: int | None = Query(None, ge=1)):
    from .research_trace import trace
    with Session() as s:
        paper = s.get(Paper, id)
        if paper is None:
            raise HTTPException(404, '论文不存在')
        analysis = s.get(Analysis, analysis_id) if analysis_id else None
        if analysis_id and (analysis is None or analysis.paper_id != id or analysis.version != version):
            raise HTTPException(404, '该分析不属于此论文版本')
        if not analysis_id and paper.version != version:
            raise HTTPException(409, '论文版本已更新，请重新打开阅读器')
        return trace(s, paper, analysis)


@app.get('/api/paper/pdf')
def paper_pdf(id:str,version:int=Query(ge=1)):
    with Session() as s:
        if not s.get(Paper,id): raise HTTPException(404,'论文不存在')
    path=DATA/'documents'/f'{hashlib.sha256(id.encode()).hexdigest()}v{version}.pdf'
    if not path.exists(): raise HTTPException(404,'此版本 PDF 尚未下载，请先完成全文分析或前往 arXiv 阅读')
    return FileResponse(path,media_type='application/pdf',headers={'Content-Disposition':'inline'})

@app.patch('/api/paper/state')
def paper_state(id:str,data:StateInput):
    with Session.begin() as s:
        p=s.get(Paper,id)
        if not p: raise HTTPException(404,'论文不存在')
        for k,v in data.model_dump(exclude_none=True).items(): setattr(p,k,v)
    return {'ok':True}

@app.get('/api/overview')
def overview(domain_id:str|None=None,days:int=Query(30,ge=7,le=365)):
    with Session() as s:
        revision=s.get(Setting,'revision').value['id']
    with overview_lock: return overview_cached(domain_id,days,revision,datetime.now(timezone.utc).date().isoformat())

overview_lock=RLock()
@lru_cache(maxsize=32)
def overview_cached(domain_id,days,revision,date_key):
    with Session() as s:
        base=paper_query(domain_id,days=days).subquery()
        total=s.scalar(select(func.count()).select_from(base))
        daily=s.execute(select(func.substr(base.c.published,1,10),func.count()).group_by(func.substr(base.c.published,1,10)).order_by(func.substr(base.c.published,1,10))).all()
        saved=s.scalar(select(func.count()).select_from(base).where(base.c.saved==True))
        aq=select(Analysis.paper_id,Analysis.domain_id,Analysis.result['topics'],Analysis.result['methods']).join(base,(base.c.id==Analysis.paper_id)&(base.c.version==Analysis.version)).join(Domain,Domain.id==Analysis.domain_id).where(Analysis.taxonomy_version==Domain.taxonomy_version).order_by(Analysis.created.desc())
        if domain_id: aq=aq.where(Analysis.domain_id==domain_id)
        topics=Counter(); methods=Counter(); pairs=Counter(); seen=set();processed=set();topic_records=set();method_records=set();pair_records=set()
        for pid,did,ts,ms in s.execute(aq):
            if (pid,did) in processed: continue
            processed.add((pid,did));seen.add(pid)
            topic_records.update((pid,t) for t in ts);method_records.update((pid,m) for m in ms)
            pair_records.update((pid,t,m) for t in ts for m in ms)
        topics.update(t for _,t in topic_records);methods.update(m for _,m in method_records);pairs.update((t,m) for _,t,m in pair_records)
        category_rows=s.execute(select(base.c.categories)).all(); cats=Counter()
        for (cs,) in category_rows: cats.update(set(cs))
        announcements=s.scalar(select(func.count()).select_from(base).where(base.c.date_basis=='announcement'))
        return {'total':total,'saved':saved,'analyzed':len(seen),'announcements':announcements,'daily':[{'date':d,'count':n} for d,n in daily], 'topics':[{'name':k,'value':v} for k,v in topics.most_common(12)],'methods':[{'name':k,'value':v} for k,v in methods.most_common(10)],'matrix':[{'topic':t,'method':m,'value':v} for (t,m),v in pairs.items()], 'categories':[{'name':k,'value':v} for k,v in cats.most_common(8)],'generated_at':now()}

@app.get('/api/jobs')
def jobs(domain_id:str|None=None):
    members=func.json_each(Job.payload, '$.domain_ids').table_valued('value')
    scope=or_(Job.payload['domain_id'].as_string()==domain_id,exists(select(1).select_from(members).where(members.c.value==domain_id))) if domain_id else True
    with Session() as s:
        active=list(s.scalars(select(Job).where(scope,Job.status.in_(['running','queued','waiting','paused'])).order_by(Job.created)))
        recent=list(s.scalars(select(Job).where(scope,Job.status.notin_(['running','queued','waiting','paused'])).order_by(Job.created.desc()).limit(60)))
        order={'running':0,'waiting':1,'paused':2,'queued':3}
        hidden={r.key[len('job-hidden:'):] for r in s.scalars(select(Setting).where(Setting.key.like('job-hidden:%')))}
        result=[]
        for j in sorted(active,key=lambda j:order[j.status])+recent:
            if j.result.get('hidden') or j.id in hidden:continue
            item=serialize(j)
            if j.result.get('cancel_requested') and j.status!='running':item['status']='cancelled'
            result.append(item)
        return result

@app.post('/api/ingest',status_code=202)
def ingest(data:IngestInput):
    with Session() as s: must_domain(s,data.domain_id)
    return {'job_id':enqueue('ingest',data.model_dump())}

@app.post('/api/analyze',status_code=202)
def analyze(id:str,data:AnalysisInput):
    require_model()
    with Session() as s:
        must_domain(s,data.domain_id)
        if not s.get(Paper,id): raise HTTPException(404,'论文不存在')
        limit=s.get(Setting,'llm').value['daily_limit']
        count=s.scalar(select(func.count()).select_from(Job).where(Job.kind.in_(['analyze','survey']),Job.status!='waiting',Job.created>=datetime.now(timezone.utc).date().isoformat()))
        if count>=limit: raise HTTPException(429,'已达到每日分析任务上限，请明天继续或在设置中调整')
    return {'job_id':enqueue('analyze',{'paper_id':id,'domain_id':data.domain_id})}

@app.post('/api/jobs/retry-all',status_code=202)
def retry_all(domain_id:str|None=None):
    retried=0;skipped=0;has_key=bool(get_key())
    with Session.begin() as s:
        if s.bind.dialect.name=='sqlite':s.connection().exec_driver_sql('BEGIN IMMEDIATE')
        active=[(j.kind,j.payload) for j in s.scalars(select(Job).where(Job.status.in_(['queued','running'])))]
        for j in s.scalars(select(Job).where(Job.status.in_(['failed','waiting'])).order_by(Job.created)):
            if domain_id and j.payload.get('domain_id')!=domain_id and domain_id not in j.payload.get('domain_ids',[]):continue
            budget=j.result.get('stage')=='awaiting_budget' or (j.status=='waiting' and '额度' in j.message)
            cancelled=j.result.get('cancel_requested') or j.result.get('hidden') or '已取消' in j.message
            needs_key=j.kind in ('analyze','survey','lesson','test_llm','signals') or (j.kind=='explore' and any(step in j.payload.get('steps',[]) for step in ['fetch','analyze']))
            if budget or cancelled or (needs_key and not has_key) or (j.kind,j.payload) in active:
                skipped+=1;continue
            if j.status=='waiting' and not (j.kind=='explore' and 'arXiv' in j.message):
                skipped+=1;continue
            j.status='queued';j.finished=None;j.message='一键重试：已重新排队，保留已完成数据'
            j.result={k:v for k,v in j.result.items() if k not in ('resume_after','cancel_requested')}
            active.append((j.kind,j.payload));retried+=1
    return {'retried':retried,'skipped':skipped}

@app.post('/api/jobs/{jid}/retry',status_code=202)
def retry(jid:str):
    with Session.begin() as s:
        j=s.get(Job,jid)
        if not j or j.status!='failed': raise HTTPException(409,'只能重试失败的任务')
        if j.result.get('cancel_requested') or j.result.get('hidden'):raise HTTPException(409,'任务已取消或删除')
        from .query_identity import payload_identity
        if any(payload_identity(other.payload)==payload_identity(j.payload) for other in s.scalars(select(Job).where(Job.kind==j.kind,Job.status.in_(['running','queued','paused','waiting'])))):
            raise HTTPException(409,'已有同一任务正在执行或等待，请使用现有任务')
        if j.kind in ('analyze','survey','lesson','test_llm'): require_model()
        j.status='queued'; j.progress=0; j.message='已重新排队'; j.finished=None
        if j.kind=='explore':j.result={k:v for k,v in j.result.items() if k!='cancel_requested'}
    return {'job_id':jid}

@app.get('/api/settings')
def settings():
    with Session() as s: return dict(s.get(Setting,'llm').value,has_key=bool(get_key()))

@app.put('/api/settings')
def configure(data:SettingsInput):
    if data.api_key: save_key(data.api_key.strip())
    with Session.begin() as s:
        previous=s.get(Setting,'llm').value['daily_limit']
        if data.daily_limit>previous:
            for job in s.scalars(select(Job).where(Job.status=='waiting')):
                if (job.kind=='explore' and job.result.get('stage')=='awaiting_budget') or (job.kind=='analyze' and '额度' in job.message):
                    job.result={**job.result,'resume_after':now()}
                    job.message='每日任务上限已调高，等待后台恢复分析'
        s.get(Setting,'llm').value={'model':data.model.strip(),'base_url':'https://api.deepseek.com','daily_limit':data.daily_limit,'auto_analyze':data.auto_analyze}
    return settings()

@app.post('/api/settings/test',status_code=202)
def test_model():
    require_model(); return {'job_id':enqueue('test_llm',{})}

@app.get('/api/surveys')
def surveys(domain_id:str|None=None):
    with Session() as s:
        q=select(Survey)
        if domain_id: q=q.where(Survey.domain_id==domain_id)
        return [serialize(row) for row in s.scalars(q.order_by(Survey.created.desc()))]

@app.post('/api/surveys',status_code=201)
async def upload_survey(domain_id:str=Form(...),file:UploadFile=File(...)):
    with Session() as s: must_domain(s,domain_id)
    sid=uuid.uuid4().hex; path=DATA/'uploads'/f'{sid}.pdf'; path.parent.mkdir(exist_ok=True)
    size=0
    try:
        with path.open('wb') as f:
            while chunk:=await file.read(1024*1024):
                if size==0 and not chunk[:1024].lstrip().startswith(b'%PDF'): raise HTTPException(422,'请上传有效 PDF 文件')
                size+=len(chunk)
                if size>25*1024*1024: raise HTTPException(413,'PDF 超过 25MB 上限')
                f.write(chunk)
        if size==0: raise HTTPException(422,'文件为空')
        with Session.begin() as s:
            row=Survey(id=sid,domain_id=domain_id,title=(file.filename or '未命名综述')[:200],filename=path.name)
            s.add(row); s.flush(); result=serialize(row)
        return result
    except Exception:
        if path.exists(): path.unlink()
        raise

@app.post('/api/surveys/{sid}/analyze',status_code=202)
def analyze_survey(sid:str):
    require_model()
    with Session() as s:
        row=s.get(Survey,sid)
        if not row: raise HTTPException(404,'综述不存在')
        return {'job_id':enqueue('survey',{'survey_id':sid,'domain_id':row.domain_id})}

@app.post('/api/surveys/{sid}/publish')
def publish(sid:str):
    with Session.begin() as s:
        row=s.get(Survey,sid)
        if not row or row.status!='draft': raise HTTPException(409,'没有可发布的分类草稿')
        d=must_domain(s,row.domain_id)
        d.topics=list(dict.fromkeys(t['name'] for t in row.draft['topics'])); d.taxonomy_version+=1; d.taxonomy_origin=row.title
        d.definitions=row.draft['topics']
        s.add(Taxonomy(domain_id=d.id,version=d.taxonomy_version,topics=d.topics,definitions=d.definitions,source=row.id))
        row.status='published'
        return serialize(d)

@app.get('/api/surveys/{sid}/file')
def survey_file(sid:str):
    with Session() as s:
        row=s.get(Survey,sid)
        if not row: raise HTTPException(404,'综述不存在')
        return FileResponse(DATA/'uploads'/row.filename,media_type='application/pdf')

if (ROOT/'dist').exists(): app.mount('/',StaticFiles(directory=ROOT/'dist',html=True),name='web')

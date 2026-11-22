import os, time, json, hashlib, traceback, threading
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update, case, func
from .db import *
from .sources import ArxivSource, ArxivRssSource, download_pdf
from .services import enqueue, upsert_papers
from .analysis import parse_pdf,analyze_document,DeepSeek,PROMPT_VERSION
from .secrets import get_key
from .task_control import check_pause,TaskPaused

def queue_candidates(domain,items):
    with Session() as s: config=s.get(Setting,'llm').value
    if not config.get('auto_analyze') or not get_key(): return
    with Session() as s:
        used=s.scalar(select(func.count()).select_from(Job).where(Job.kind.in_(['analyze','survey']),Job.created>=datetime.now(timezone.utc).date().isoformat()))
    for item in items:
        if used>=config['daily_limit']: break
        with Session() as s:
            existing=s.scalar(select(Analysis.id).where(Analysis.paper_id==item['id'],Analysis.version==item['version'],Analysis.domain_id==domain.id,Analysis.taxonomy_version==domain.taxonomy_version))
        if existing: continue
        enqueue('analyze',{'paper_id':item['id'],'domain_id':domain.id});used+=1

def progress(jid,percent,message):
    check_pause(jid)
    with Session.begin() as s:
        j=s.get(Job,jid); j.progress=percent; j.message=message

def run_job(j):
    from .model_runtime import execution_scope
    if j.kind=='analyze' and j.payload.get('intake_scope'):
        from .product.paper_intakes import analysis_job_allowed
        allowed,reason=analysis_job_allowed(j.id)
        if not allowed:raise ValueError(reason)
    with execution_scope(job_id=j.id,paper_id=j.payload.get('paper_id'),stage=j.kind):
        return _run_job(j)

def _run_job(j):
    with Session() as s:
        domain=s.get(Domain,j.payload['domain_id']) if j.payload.get('domain_id') else None
    if j.kind=='test_llm':
        DeepSeek().generate('Return JSON: {"connected": true}')
        return {'message':'DeepSeek 连接成功'}
    if j.kind=='explore':
        from .exploration import run_exploration
        return run_exploration(j,progress)
    if j.kind=='trends':
        from .trends import run_trends
        return run_trends(j,progress)
    if not domain: raise ValueError('研究领域不存在')
    if j.kind=='lesson':
        from .lessons import build_lesson
        with Session() as s:
            a=s.get(Analysis,j.payload['analysis_id'])
            existing=s.get(MethodLesson,(j.payload['analysis_id'],j.payload['claim_index']))
        if existing and not j.payload.get('force'):return {'message':'方法讲解已生成'}
        if not a:raise ValueError('原分析不存在')
        provider=DeepSeek()
        progress(j.id,20,'正在阅读方法原文，编写数学推导与符号说明')
        result=build_lesson(a,j.payload['claim_index'],provider)
        with Session.begin() as s:
            s.merge(MethodLesson(analysis_id=a.id,claim_index=j.payload['claim_index'],result=result,model=provider.config['model']));touch(s)
        return {'message':'方法数学讲解已生成，来源片段已核验'}
    if j.kind=='ingest':
        source=ArxivSource(); start=j.payload.get('start',0); added=0; changed=0; seen=0
        cutoff=datetime.fromisoformat(j.payload['cutoff']) if j.payload.get('cutoff') else datetime.now(timezone.utc)-timedelta(days=j.payload.get('days',30))
        query=j.payload.get('query',domain.query)
        complete=False
        for batch in range(5):
            progress(j.id,10+batch*16,f'正在同步 arXiv，已检查 {start} 条记录')
            try: items,total=source.fetch(query,start,100)
            except (RuntimeError,ValueError) as exc:
                progress(j.id,20,'历史 API 不可用，正在读取官方每日 RSS')
                items=ArxivRssSource().fetch_daily(query)
                n,u=upsert_papers(domain.id,items)
                queue_candidates(domain,items)
                message=f'RSS 公告：新增 {n} 篇，更新 {u} 篇；历史 API 未连接，近 {j.payload.get("days",30)} 天回填未完成'
                with Session.begin() as s: s.get(Domain,domain.id).sync_note=message
                return {'new':n,'updated':u,'complete':False,'source':'rss','message':message}
            eligible=[p for p in items if datetime.fromisoformat(p['updated'].replace('Z','+00:00'))>=cutoff]
            n,u=upsert_papers(domain.id,eligible); added+=n; changed+=u; seen+=len(eligible)
            queue_candidates(domain,eligible)
            start+=len(items)
            if not items or start>=total or len(eligible)<len(items): complete=True; break
        if complete:
            with Session.begin() as s:
                d=s.get(Domain,domain.id);d.last_sync=now();d.sync_note='历史 API 增量同步完成'
        else:
            enqueue('ingest',{'domain_id':domain.id,'start':start,'cutoff':cutoff.isoformat(),'query':query})
        return {'new':added,'updated':changed,'seen':seen,'complete':complete,'message':f'新增 {added} 篇，更新 {changed} 篇'+('' if complete else '；后续批次已排队')}
    if j.kind in ('analyze','survey'):
        provider=DeepSeek()  # Fail before downloading/parsing if not configured.
        if j.kind=='survey':
            with Session() as s: survey=s.get(Survey,j.payload['survey_id'])
            path=DATA/'uploads'/survey.filename
        else:
            with Session() as s: paper=s.get(Paper,j.payload['paper_id'])
            if not paper: raise ValueError('论文不存在')
            if j.payload.get('intake_scope'):
                from .product.intake_runtime import assert_analysis_target
                assert_analysis_target(j,paper,domain,provider)
            path=DATA/'documents'/f'{hashlib.sha256(paper.id.encode()).hexdigest()}v{paper.version}.pdf'
            path.parent.mkdir(exist_ok=True)
            if not path.exists():
                progress(j.id,5,'正在获取论文全文')
                try: download_pdf(paper.id,paper.version,path)
                except Exception:
                    if path.exists(): path.unlink()
                    raise
        progress(j.id,12,'正在解析全文与页码')
        pages,digest=parse_pdf(path)
        if j.kind=='analyze' and j.payload.get('intake_scope'):
            assert_analysis_target(j,paper,domain,provider,digest)
            from .analysis_repository import assert_current
            with Session() as s:assert_current(s,paper,domain,digest)
        if j.kind=='analyze':
            from .analysis_repository import find_cached
            with Session() as s:
                cached=find_cached(s,paper,domain,digest,provider)
                if cached:
                    from .analysis_repository import assert_current
                    assert_current(s,paper,domain,digest)
                    check_pause(j.id)
                    return {'message':'已复用当前版本的分析结果'}
        result=analyze_document(pages,domain,survey=j.kind=='survey',model=provider,progress=lambda p,m:progress(j.id,p,m),cache_dir=DATA/'analysis-cache',synthesize=True)
        from .analysis_repository import assert_current,provider_fingerprint
        result['pipeline_fingerprint']=provider_fingerprint(provider)
        check_pause(j.id)
        with Session.begin() as s:
            s.connection().exec_driver_sql('BEGIN IMMEDIATE')
            if j.kind=='survey':
                current_domain=s.get(Domain,domain.id)
                if not current_domain or current_domain.taxonomy_version!=domain.taxonomy_version:
                    raise RuntimeError('分类版本已变化；综述候选缓存保留，请重试')
                survey=s.get(Survey,j.payload['survey_id']); survey.draft=result; survey.status='draft'
            else:
                assert_current(s,paper,domain,digest)
                if j.payload.get('intake_scope'):assert_analysis_target(j,paper,domain,provider,digest)
                if find_cached(s,paper,domain,digest,provider):
                    return {'message':'已复用并发任务已发布的当前版本分析'}
                s.add(Analysis(paper_id=paper.id,domain_id=domain.id,version=paper.version,taxonomy_version=domain.taxonomy_version,model=provider.config['model'],content_hash=digest,result=result))
                from .tags import import_result
                import_result(s,paper.id,result)
            touch(s)
        return {'message':'综述分类草稿已生成' if j.kind=='survey' else '全文分析完成，证据可查看'}
    raise ValueError('未知任务类型')

def main():
    init_db()
    lock=open(DATA/'worker.lock','a+b'); lock.seek(0); lock.write(b'1'); lock.flush(); lock.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError: raise SystemExit('Another worker is running')
    def heartbeat():
        while True:
            (DATA/'worker.heartbeat').write_text(str(time.time()))
            time.sleep(5)
    threading.Thread(target=heartbeat,daemon=True).start()
    with Session.begin() as s:
        from .product.intake_runtime import runtime_active
        for j in s.scalars(select(Job).where(Job.status=='running',Job.kind!='trend_download')):
            if j.result.get('intake_run_token') and runtime_active():continue
            j.status='failed'; j.message='上次运行中断，可手动重试'; j.finished=now()
    last_schedule=0
    while True:
        (DATA/'worker.heartbeat').write_text(str(time.time()))
        with Session() as s:
            gate=s.get(Setting,'background_control');globally_paused=bool(gate and gate.value.get('paused'))
        if globally_paused:time.sleep(1);continue
        if not (gate and gate.value.get('manual_only')) and time.time()-last_schedule>60:
            last_schedule=time.time()
            with Session() as s:
                domains=list(s.scalars(select(Domain).where(Domain.auto_sync==True)))
                auto_analyze=s.get(Setting,'llm').value.get('auto_analyze',False)
                recent=list(s.scalars(select(Job).where(Job.kind.in_(['ingest','explore']),Job.created> (datetime.now(timezone.utc)-timedelta(hours=24)).isoformat())))
            for d in domains:
                if not any(j.payload.get('domain_id')==d.id or d.id in j.payload.get('domain_ids',[]) for j in recent):
                    today=datetime.now(timezone.utc).date()
                    enqueue('explore',{'domain_ids':[d.id],'start':today.replace(day=1).isoformat(),'end':today.isoformat(),'query':'','steps':['search','fetch','analyze','statistics'] if auto_analyze else ['search','statistics'],'target':3,'maximum':6,'threshold':70,'exceptional':85,'scopes':[{'domain_id':d.id,'name':d.name,'query':d.query,'taxonomy_version':d.taxonomy_version}]})
        with Session.begin() as s:
            s.connection().exec_driver_sql('BEGIN IMMEDIATE')
            gate=s.get(Setting,'background_control')
            if gate and gate.value.get('paused'):continue
            for waiting in s.scalars(select(Job).where(Job.status=='waiting',Job.kind.in_(['explore','trends']))):
                if waiting.result.get('resume_after','9999')<=now():waiting.status='queued';waiting.message='每日额度已恢复，继续探索'
            day=datetime.now(timezone.utc).date().isoformat()
            used=s.scalar(select(func.count()).select_from(Job).where(Job.kind.in_(['analyze','survey']),Job.created>=day,Job.status!='waiting'))
            allowance=max(0,s.get(Setting,'llm').value['daily_limit']-used)
            for deferred in s.scalars(select(Job).where(Job.status=='waiting',Job.kind=='analyze').order_by(Job.created).limit(allowance)):
                if deferred.result.get('resume_after','9999')<=now():
                    deferred.status='queued';deferred.created=now();deferred.message='分析额度已恢复，等待全文分析'
            selection=select(Job).where(Job.status=='queued',Job.kind!='trend_download')
            if gate and gate.value.get('manual_only'):selection=selection.where(Job.id.in_(gate.value.get('allowed_ids',[])))
            job=s.scalar(selection.order_by(case((Job.kind.in_(['lesson','test_llm']),-1),(Job.kind.in_(['analyze','survey','trends']),0),(Job.kind=='explore',1),else_=2),Job.created).limit(1))
            if job: job.status='running'; job.message='后台任务开始'
        if not job: time.sleep(1); continue
        try:
            result=run_job(job)
            with Session.begin() as s:
                row=s.get(Job,job.id); row.status='waiting' if result.get('resume_after') else 'done'; row.progress=row.progress if result.get('resume_after') else 100; row.result=result; row.message=result.get('message','完成'); row.finished=None if result.get('resume_after') else now()
        except TaskPaused as exc:
            with Session.begin() as s:
                row=s.get(Job,job.id);row.status='paused';row.message=str(exc);row.finished=None
        except Exception as exc:
            with Session.begin() as s:
                row=s.get(Job,job.id)
                if job.kind in ('explore','trends') and 'arXiv 官方历史检索暂时不可用' in str(exc) and row.result.get('network_retries',0)<4:
                    row.status='waiting';row.result={**row.result,'network_retries':row.result.get('network_retries',0)+1,'resume_after':(datetime.now(timezone.utc)+timedelta(minutes=30)).isoformat()};row.message='arXiv 暂时不可用，30 分钟后自动续传';row.finished=None
                else:row.status='failed';row.message=str(exc)[:600];row.finished=now()

if __name__=='__main__': main()

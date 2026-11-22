"""User-uploaded papers join the same PDF reader and full-text analysis pipeline."""
import hashlib,uuid
from datetime import date,datetime,timezone
from pathlib import Path
from fastapi import APIRouter,UploadFile,File,Form,HTTPException
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select,func
from pypdf import PdfReader
from .db import Session,DATA,Paper,Domain,Membership,Version,Job,Setting,now,touch,Analysis
from .services import enqueue
from .secrets import get_key
from .analysis import PROMPT_VERSION
router=APIRouter(prefix='/api/paper')

def finish(path,domain_id,title,published,filename,analyze):
    try:
        pdf=PdfReader(path)
        if pdf.is_encrypted:raise HTTPException(422,'请先解除 PDF 密码保护后上传')
        if not len(pdf.pages) or len(pdf.pages)>1000:raise HTTPException(422,'PDF 应包含 1–1000 页')
        metadata=pdf.metadata or {};auto_title=str(metadata.get('/Title','')).strip()
        author=str(metadata.get('/Author','')).strip()
        if not title:title=auto_title if auto_title and len(auto_title)<500 else Path(filename).stem
    except HTTPException:raise
    except Exception:raise HTTPException(422,'无法读取此 PDF，请检查文件是否完整') from None
    digest=hashlib.sha256(path.read_bytes()).hexdigest();pid='local-'+digest
    target=DATA/'documents'/f'{hashlib.sha256(pid.encode()).hexdigest()}v1.pdf';target.parent.mkdir(exist_ok=True)
    with Session.begin() as s:
        if not s.get(Domain,domain_id):raise HTTPException(404,'研究领域不存在')
        existing=s.get(Paper,pid);duplicate=existing is not None
        if not existing:
            item=dict(id=pid,version=1,title=title[:500] or '未命名文献',abstract='',authors=[author] if author else [],categories=['本地导入'],published=(published or date.today().isoformat())+'T00:00:00+00:00',updated=now(),date_basis='submitted' if published else 'imported')
            s.add(Paper(**item));s.add(Version(paper_id=pid,version=1,metadata_json=item))
        if not s.get(Membership,(domain_id,pid)):s.add(Membership(domain_id=domain_id,paper_id=pid))
        if not target.exists():path.replace(target)
        touch(s)
    job_id=None;message='文献已收录，可直接阅读 PDF'
    if analyze:
        with Session() as s:
            pending=s.scalar(select(Job).where(Job.kind=='analyze',Job.status.in_(['queued','running'])).filter(Job.payload['paper_id'].as_string()==pid,Job.payload['domain_id'].as_string()==domain_id))
            settings=s.get(Setting,'llm').value
            domain=s.get(Domain,domain_id)
            analyzed=s.scalar(select(Analysis.id).where(Analysis.paper_id==pid,Analysis.domain_id==domain_id,Analysis.version==1,Analysis.taxonomy_version==domain.taxonomy_version,Analysis.model==settings['model'],Analysis.result['prompt_version'].as_string()==PROMPT_VERSION))
            count=s.scalar(select(func.count()).select_from(Job).where(Job.kind.in_(['analyze','survey']),Job.status!='waiting',Job.created>=datetime.now(timezone.utc).date().isoformat()))
            limit=s.get(Setting,'llm').value['daily_limit']
        if pending:job_id=pending.id;message='已复用现有全文分析任务'
        elif analyzed:message='已复用已有文献与分析结果'
        elif not get_key():message='文献已收录；配置模型连接后可发起全文分析'
        elif count>=limit:message='文献已收录；今日分析额度已用完，可在额度恢复后点击全文分析'
        else:job_id=enqueue('analyze',{'paper_id':pid,'domain_id':domain_id});message='文献已收录，全文分析已加入后台队列'
    return {'paper_id':pid,'duplicate':duplicate,'job_id':job_id,'message':message}

@router.post('/import',status_code=201)
async def upload(domain_id:str=Form(...),file:UploadFile=File(...),title:str=Form('',max_length=500),published:str=Form(''),analyze:bool=Form(True)):
    with Session() as s:
        if not s.get(Domain,domain_id):raise HTTPException(404,'研究领域不存在')
    if published:
        try:
            if date.fromisoformat(published)>date.today():raise ValueError()
        except ValueError:raise HTTPException(422,'发表日期应为不晚于今天的 YYYY-MM-DD')
    folder=DATA/'uploads';folder.mkdir(exist_ok=True);path=folder/f'import-{uuid.uuid4().hex}.pdf';size=0
    try:
        with path.open('wb') as out:
            while chunk:=await file.read(1024*1024):
                if not size and not chunk[:1024].lstrip().startswith(b'%PDF'):raise HTTPException(422,'请上传有效 PDF 文件')
                size+=len(chunk)
                if size>100*1024*1024:raise HTTPException(413,'单篇 PDF 最大 100MB')
                out.write(chunk)
        if not size:raise HTTPException(422,'文件为空')
        return await run_in_threadpool(finish,path,domain_id,title.strip(),published,file.filename or '未命名文献.pdf',analyze)
    finally:
        path.unlink(missing_ok=True);await file.close()

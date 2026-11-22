"""One bounded, fenced runner for explicitly linked paper intakes only.

It never starts the global worker, changes its gates, or resumes paused jobs.
Official source text is metadata, never instructions. Tests disable the thread
and exercise process_once with bounded source/model doubles.
"""
import hashlib
import os
import re
import threading
import time
import uuid

import httpx
from pypdf import PdfReader
from sqlalchemy import exists, select

from ..db import DATA, Domain, Job, Paper, Session, Setting, Version, now, serialize
from ..sources import arxiv_wait, download_pdf, parse_atom
from ..task_control import TaskPaused
from ..evidence_contracts import PIPELINE_VERSION
from .models import ProjectPaperIntake
from . import paper_intakes, service

_stop = threading.Event()
_thread = None
_lock = None
HEARTBEAT = DATA / 'intake-runtime.heartbeat'


def runtime_active():
    try:
        return time.time() - HEARTBEAT.stat().st_mtime < 15
    except OSError:
        return False


def _paused(s):
    gate = s.get(Setting, 'background_control')
    return bool(gate and gate.value.get('paused'))


def checkpoint(jid, token, progress=None, message=None, extra=None):
    if _stop.is_set():
        raise TaskPaused('定向收录服务已停止，已完成阶段仍保留')
    context = paper_intakes.transaction if any(v is not None for v in (progress,message,extra)) else Session
    with context() as s:
        job = s.get(Job, jid)
        if (not job or job.status != 'running' or job.result.get('intake_run_token') != token
                or job.result.get('cancel_requested') or job.result.get('hidden')
                or job.result.get('pause_requested') or (_paused(s) and not job.result.get('intake_explicit'))):
            raise TaskPaused('任务已暂停、取消或执行者已变化，未继续执行')
        if progress is not None:
            job.progress = progress
        if message is not None:
            job.message = message
        if extra:
            job.result = {**job.result, **extra}


def fetch_metadata(paper_id, requested_version=None):
    """Resolve an exact ID through the fixed official Atom endpoint."""
    paper_id, embedded = paper_intakes.canonical_id(paper_id)
    requested_version = requested_version or embedded
    exact_id = paper_id + (f'v{requested_version}' if requested_version else '')
    arxiv_wait()
    response = httpx.get('https://export.arxiv.org/api/query', params={'id_list': exact_id},
        timeout=45, follow_redirects=False, headers={'User-Agent': 'ResearchAtlas/0.3 local research intake'})
    response.raise_for_status()
    items, _ = parse_atom(response.text)
    item = next((p for p in items if p['id'] == paper_id), None)
    if (not item or type(item.get('version')) is not int or item['version'] < 1
            or (requested_version and item['version'] != requested_version)
            or not item.get('title', '').strip()):
        raise ValueError('官方元数据未返回所请求的论文编号与版本，未收录其他文献')
    return item


def inspect_pdf(path, paper):
    """Check readability and obvious source identity mismatches before publish."""
    with path.open('rb') as source:
        if not source.read(1024).lstrip().startswith(b'%PDF'):
            raise ValueError('下载内容不是有效PDF')
    reader = PdfReader(path)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= 1000:
        raise ValueError('PDF受密码保护、为空或超过1000页，未关联为已下载原文')
    first = '\n'.join((page.extract_text() or '')[:12000] for page in reader.pages[:2])
    header = re.search(r'arxiv\s*:\s*((?:\d{4}\.\d{4,5}|[a-z][a-z.-]*/\d{7})(?:v\d+)?)', first, re.I)
    if header:
        pid, version = paper_intakes.canonical_id(header[1])
        if pid.lower() != paper['id'].lower() or (version and version != paper['version']):
            raise ValueError('PDF首页的论文编号或版本与官方元数据不一致，未发布收录结果')
    words = set(re.findall(r'[a-z0-9]{3,}', paper['title'].lower()))
    text_words = set(re.findall(r'[a-z0-9]{3,}', first.lower()))
    title_match = bool(words and len(words & text_words) / len(words) >= .7)
    return {'pages': len(reader.pages), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'identity_check': {'verified': bool(header or title_match),
            'method': 'official-id-version-url-and-first-pages',
            'page_id_found': bool(header), 'title_text_match': title_match}}


def run_download(job, token):
    pid, requested = paper_intakes.canonical_id(job.payload['paper_id'])
    requested = job.payload.get('requested_version') or requested
    checkpoint(job.id, token, 5, '正在核对论文编号与官方元数据')
    # Restart/retry retains the version resolved by this particular download.
    paper = job.result.get('metadata_snapshot')
    if not isinstance(paper, dict) or paper.get('id') != pid or not paper.get('version'):
        paper = None
    if paper is None:
        with Session() as s:
            local = s.get(Paper, pid)
            version = requested or (local.version if local else None)
            record = s.get(Version, (pid, version)) if version else None
            if local and version and paper_intakes.pdf_path(pid, version).exists():
                paper = dict(record.metadata_json) if record else serialize(local)
                paper = {k:v for k,v in paper.items() if k in ('id','version','title','abstract','authors','categories','published','updated','date_basis')}
        if paper is None:
            paper = fetch_metadata(pid, requested)
    if paper['id'] != pid or (requested and paper['version'] != requested):
        raise ValueError('论文编号或版本与本次请求不一致')
    version = paper['version']
    checkpoint(job.id, token, 15, '已核对元数据，正在获取对应版本PDF',
        {'metadata_snapshot': paper, 'resolved_version': version})
    target = paper_intakes.pdf_path(pid, version)
    target.parent.mkdir(parents=True, exist_ok=True)
    validation = None
    expected_hash = job.result.get('sha256')
    if target.exists():
        try:
            validation = inspect_pdf(target, paper)
            if expected_hash and validation['sha256'] != expected_hash:
                raise ValueError('原文件哈希与本次任务已保存的版本不同')
        except Exception:
            # An explicit repair keeps the rejected bytes for inspection. A
            # valid historical version is never overwritten in place.
            rejected_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            rejected = target.with_name(target.stem+'.rejected-'+rejected_hash+'.pdf')
            if not rejected.exists(): os.link(target, rejected)
            target.unlink()
            validation = None
    if validation is None:
        staged = target.with_name(target.stem + '.intake-' + job.id + '-' + token + '.pdf')
        try:
            download_pdf(pid, version, staged)
            validation = inspect_pdf(staged, paper)
            if expected_hash and validation['sha256'] != expected_hash:
                raise ValueError('同一版本PDF与已记录哈希不同，需核对来源后再收录；旧文件已保留')
            checkpoint(job.id, token, 75, '正在校验PDF页数与来源版本')
            # Never overwrite an existing version, including a concurrently
            # downloaded original. Hard-link creation is atomic on this volume.
            try:
                os.link(staged, target)
            except FileExistsError:
                validation = inspect_pdf(target, paper)
        finally:
            staged.unlink(missing_ok=True)
    result = {'paper': paper, 'version': version, **validation,
        'pdf_url': f'https://arxiv.org/pdf/{pid}v{version}',
        'metadata_url': f'https://export.arxiv.org/api/query?id_list={pid}v{version}'}
    checkpoint(job.id, token, 90, 'PDF已校验，正在关联原项目线索', {'verified_download': result})
    paper_intakes.finish_download(job.id, result, token)


def assert_analysis_target(job, paper, domain, provider, content_hash=None):
    if not job.payload.get('intake_scope'):
        return
    expected = job.payload.get('intake_target') or {}
    config = provider.config
    identity = service.digest({'model': config.get('model'), 'base_url': config.get('base_url'), 'pipeline': PIPELINE_VERSION})
    if (not expected or expected.get('paper_version') != paper.version
            or expected.get('taxonomy_version') != domain.taxonomy_version
            or expected.get('model') != config.get('model') or expected.get('model_identity') != identity
            or (content_hash is not None and expected.get('content_hash') != content_hash)):
        raise ValueError('分析目标版本、解析来源或模型身份已变化，未分析另一版本')
    token = job.result.get('intake_run_token')
    if token:
        checkpoint(job.id, token)


def _claim():
    with paper_intakes.transaction() as s:
        linked_download = exists(select(ProjectPaperIntake.id).where(ProjectPaperIntake.download_job_id == Job.id))
        linked_analysis = exists(select(ProjectPaperIntake.id).where(ProjectPaperIntake.analysis_job_id == Job.id))
        query = select(Job).where(Job.status == 'queued', Job.payload['intake_scope'].as_boolean() == True,
            ((Job.kind == 'trend_download') & linked_download) | ((Job.kind == 'analyze') & linked_analysis))
        for job in s.scalars(query.order_by(Job.created)):
            if job.result.get('pause_requested') or job.result.get('cancel_requested') or job.result.get('hidden'):
                continue
            if _paused(s) and not job.result.get('intake_explicit'):
                continue
            token = uuid.uuid4().hex
            job.status, job.message, job.finished = 'running', '定向收录任务开始', None
            job.result = {**job.result, 'intake_run_token': token, 'intake_started': now()}
            s.flush()
            return job, token
    return None


def _finish(jid, token, status, message, result=None):
    with paper_intakes.transaction() as s:
        job = s.get(Job, jid)
        if not job or job.result.get('intake_run_token') != token or job.status != 'running':
            return
        if job.result.get('cancel_requested'):
            status, message = 'cancelled', '已取消，保留已完成阶段和来源文件'
        elif job.result.get('pause_requested') or (_paused(s) and not job.result.get('intake_explicit')):
            status, message = 'paused', '已暂停，保留已完成阶段和来源文件'
        job.status, job.message = status, message[:600]
        job.finished = now() if status in ('done','failed','cancelled') else None
        if status == 'done': job.progress = 100
        if result: job.result = {**job.result, **result}


def process_once():
    claimed = _claim()
    if not claimed:
        paper_intakes.reconcile()
        return False
    job, token = claimed
    try:
        if job.kind == 'trend_download':
            run_download(job, token)
        else:
            allowed, blocker = paper_intakes.analysis_job_allowed(job.id)
            if not allowed:
                _finish(job.id, token, 'failed', blocker, {'intake_blocker': blocker})
            else:
                from ..worker import run_job
                result = run_job(job)
                _finish(job.id, token, 'done', result.get('message','全文分析已完成'), result)
    except TaskPaused as exc:
        _finish(job.id, token, 'paused', str(exc))
    except Exception as exc:
        _finish(job.id, token, 'failed', str(exc))
    paper_intakes.reconcile()
    return True


def _recover():
    with paper_intakes.transaction() as s:
        for job in s.scalars(select(Job).where(Job.status == 'running')):
            if not job.payload.get('intake_scope') or not job.result.get('intake_run_token'):
                continue
            job.status, job.finished = 'failed', now()
            job.message = '上次定向收录执行中断，来源缓存已保留；请明确重试'
    paper_intakes.reconcile()


def _loop():
    def heartbeat():
        while not _stop.is_set():
            HEARTBEAT.write_text(str(os.getpid()), encoding='ascii')
            _stop.wait(4)
    threading.Thread(target=heartbeat, name='atlas-intake-heartbeat', daemon=True).start()
    try:
        _recover()
        while not _stop.is_set():
            try:
                if not process_once(): _stop.wait(2)
            except Exception:
                # A transient DB contention must not terminate the bounded runner.
                _stop.wait(2)
    finally:
        if _lock: _lock.close()
        HEARTBEAT.unlink(missing_ok=True)


def start():
    global _thread, _lock
    if os.environ.get('ATLAS_SCOPED_INTAKE_DISABLED') == '1' or (_thread and _thread.is_alive()):
        return
    lock = open(DATA/'intake-runtime.lock', 'a+b')
    lock.seek(0); lock.write(b'1'); lock.flush(); lock.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        lock.close()
        return
    _lock = lock
    _stop.clear()
    _thread = threading.Thread(target=_loop, name='atlas-paper-intakes', daemon=True)
    _thread.start()


def stop():
    _stop.set()
    if _thread: _thread.join(timeout=.5)

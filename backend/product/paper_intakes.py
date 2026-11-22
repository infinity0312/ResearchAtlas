"""Project-scoped intake persistence. Network/execution lives in intake_runtime.

Only explicit writes and successful download publication enqueue analysis.
Reconciliation and GETs never revive or schedule work.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import re
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select

from ..db import Analysis, DATA, Domain, Job, Membership, Paper, Session, Setting, Version, now, serialize, touch
from ..analysis_repository import effective_hash, source_updates
from ..evidence_contracts import PIPELINE_VERSION
from ..model_runtime import ModelUsage, accounting_day, _totals
from ..secrets import get_key
from .contracts import CandidateCreate
from .models import ProjectPaperIntake, ProjectTrendLead, ResearchProject
from . import research_flow, service

ACTIVE = ('queued', 'running', 'paused', 'waiting')


@contextmanager
def transaction():
    with Session.begin() as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE')
        yield s


def canonical_id(value):
    match = re.fullmatch(r'(\d{4}\.\d{4,5}|[A-Za-z][A-Za-z.-]*/\d{7})(?:v([1-9]\d*))?', value)
    if not match:
        raise HTTPException(422, '样本需要有效arXiv编号，不能使用自定义地址下载')
    return match[1], int(match[2]) if match[2] else None


def pdf_path(paper_id, version):
    return DATA / 'documents' / (hashlib.sha256(paper_id.encode()).hexdigest()+f'v{version}.pdf')


def verified_file(paper_id, version, sha256):
    if type(version) is not int or version < 1 or not isinstance(sha256, str):
        return False
    path = pdf_path(paper_id, version)
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest() == sha256
    except OSError:
        return False


def settings(s, key):
    row = s.get(Setting, key)
    return row.value if row and isinstance(row.value, dict) else {}


def analysis_blocker(s, job_id=None, explicit=False):
    job = s.get(Job, job_id) if job_id else None
    explicit = explicit or bool(job and job.payload.get('intake_scope') and job.result.get('intake_explicit'))
    if not explicit and settings(s, 'background_control').get('paused'):
        return '后台任务已暂停，未恢复任何旧任务'
    if settings(s, 'model_control').get('enabled', True) is False:
        return '模型调用已关闭'
    if not get_key():
        return '未配置模型密钥，PDF收录不受影响'
    config = settings(s, 'llm')
    day = datetime.now(timezone.utc).date().isoformat()
    count = s.scalar(select(func.count()).select_from(Job).where(Job.kind.in_(['analyze', 'survey']),
        Job.created >= day, Job.status != 'waiting'))
    if count >= config.get('daily_limit', 20) and job_id is None:
        return '每日分析任务额度已用完'
    budget = settings(s, 'model_budget')
    totals = _totals(s, ModelUsage.day == accounting_day())
    cap = budget.get('daily_tokens')
    if cap is not None and (totals['unknown_calls'] or totals['committed_tokens'] >= cap):
        return '每日模型预算不足或存在未知用量'
    if job_id:
        totals = _totals(s, ModelUsage.task_id == 'job:'+job_id)
        if budget.get('task_calls') is not None and totals['attempts'] >= budget['task_calls']:
            return '当前任务调用次数预算已用完'
        if budget.get('task_tokens') is not None and (totals['unknown_calls'] or totals['committed_tokens'] >= budget['task_tokens']):
            return '当前任务模型预算不足或存在未知用量'
    return ''


def capabilities(s):
    blocker = analysis_blocker(s, explicit=True)
    return {'analysis_enabled': not blocker, 'analysis_blocker': blocker,
            'runner_paused': bool(settings(s, 'background_control').get('paused'))}


def intake_view(s, intake):
    download = s.get(Job, intake.download_job_id)
    analysis = s.get(Job, intake.analysis_job_id) if intake.analysis_job_id else None
    ready = verified_file(intake.paper_id, intake.pdf_version, intake.pdf_sha256)
    download_result = download.result if download and isinstance(download.result, dict) else {}
    download_shared = s.scalar(select(func.count()).select_from(ProjectPaperIntake).where(
        ProjectPaperIntake.download_job_id == intake.download_job_id)) > 1
    analysis_shared = bool(analysis and (not analysis.payload.get('intake_scope') or
        s.scalar(select(func.count()).select_from(ProjectPaperIntake).where(
            ProjectPaperIntake.analysis_job_id == analysis.id)) > 1))
    return {**serialize(intake), 'actual_version': intake.pdf_version or download_result.get('downloaded_version'),
        'metadata_version': intake.metadata_snapshot.get('version') or download_result.get('metadata_snapshot', {}).get('version'), 'pdf_ready': ready,
        'paper_title': intake.metadata_snapshot.get('title') or intake.judgment_snapshot.get('sample', {}).get('title', intake.paper_id),
        'status': 'done' if ready and intake.status == 'done' else ('failed' if intake.status == 'failed' and download and download.status == 'done' else download.status if download else intake.status),
        'download_job_status': download.status if download else None,
        'analysis_job_status': analysis.status if analysis else None,
        'download_progress': download.progress if download else None,
        'download_message': download.message if download else '',
        'download_reused': download_shared,
        'analysis_reused': analysis_shared or bool(intake.analysis_id and not intake.analysis_job_id),
        'analysis_status': analysis.status if analysis and analysis.status in ACTIVE else intake.analysis_status}


def get_lead(s, pid, lid):
    project = service.project(s, pid)
    lead = s.get(ProjectTrendLead, lid)
    if lead is None or lead.project_id != pid:
        raise HTTPException(404, '项目趋势线索不存在')
    return project, lead


def get_intake(s, pid, lid, iid, revision):
    project, lead = get_lead(s, pid, lid)
    intake = s.get(ProjectPaperIntake, iid)
    if intake is None or intake.project_id != pid or intake.lead_id != lid:
        raise HTTPException(404, '项目论文收录记录不存在')
    if intake.revision != revision:
        raise HTTPException(409, '收录记录已变化，请保留输入并重新载入')
    return project, lead, intake


def record(s, intake, action, before):
    intake.revision += 1
    intake.updated = now()
    s.flush()
    service.event(s, service.project(s, intake.project_id), action,
                  {'before': before, 'after': serialize(intake)})


def target(s, intake):
    paper, domain = s.get(Paper, intake.paper_id), s.get(Domain, intake.domain_id)
    if not paper or not domain or paper.version != intake.pdf_version:
        return None
    config = settings(s, 'llm')
    updates = source_updates(s, [paper.id])
    content_hash = updates.current_by_paper.get((paper.id, paper.version)) or effective_hash(intake.pdf_sha256, updates)
    return {'paper_version': paper.version, 'taxonomy_version': domain.taxonomy_version,
        'content_hash': content_hash, 'model': config.get('model', ''),
        'model_identity': service.digest({'model': config.get('model'), 'base_url': config.get('base_url'), 'pipeline': PIPELINE_VERSION})}


def current_analysis(s, intake, expected):
    if not expected:
        return None
    for analysis in s.scalars(select(Analysis).where(Analysis.paper_id == intake.paper_id,
            Analysis.domain_id == intake.domain_id, Analysis.version == expected['paper_version'],
            Analysis.taxonomy_version == expected['taxonomy_version'], Analysis.content_hash == expected['content_hash'])
            .order_by(Analysis.id.desc())):
        view = service.analysis_view(s, analysis)
        if view and view['quality']['freshness'] == 'current' and view['quality']['grounding'] == 'bound':
            return analysis
    return None


def queue_analysis(s, intake):
    identity = intake.metadata_snapshot.get('identity_check')
    if identity is False or (isinstance(identity, dict) and identity.get('verified') is False):
        intake.analysis_status, intake.analysis_blocker = 'blocked', 'PDF身份尚未核对，需核对PDF身份后再分析'
        return
    expected = target(s, intake)
    if not expected:
        intake.analysis_status, intake.analysis_blocker = 'blocked', '论文或分类版本已变化，不能把其他版本分析挂回本次收录'
        return
    intake.analysis_target = expected
    cached = current_analysis(s, intake, expected)
    if cached:
        intake.analysis_id = cached.id
        intake.analysis_status, intake.analysis_blocker = 'done', ''
        return
    # Existing active tasks are reused, including paused tasks. Never silently revive them.
    for job in s.scalars(select(Job).where(Job.kind == 'analyze', Job.status.in_(ACTIVE)).order_by(Job.created)):
        if job.payload.get('paper_id') != intake.paper_id or job.payload.get('domain_id') != intake.domain_id:
            continue
        frozen = job.payload.get('intake_target')
        if frozen is not None and frozen != expected:
            continue
        intake.analysis_job_id = job.id
        intake.analysis_status, intake.analysis_blocker = job.status, '' if frozen else '复用已有任务等待明确版本结果，不由本功能执行无固定版本的旧任务'
        return
    blocker = analysis_blocker(s, explicit=True)
    if blocker:
        intake.analysis_status, intake.analysis_blocker = 'blocked', blocker
        return
    job = Job(id=uuid.uuid4().hex, kind='analyze', payload={'paper_id': intake.paper_id,
        'domain_id': intake.domain_id, 'intake_scope': True, 'intake_target': expected},
        result={'intake_explicit': True})
    s.add(job); s.flush()
    intake.analysis_job_id, intake.analysis_status, intake.analysis_blocker = job.id, 'queued', ''


def create(s, pid, lid, data):
    project, lead = get_lead(s, pid, lid)
    if lead.revision != data.revision:
        raise HTTPException(409, '趋势线索已变化，请保留选择并重新载入')
    sample = next((p for p in lead.snapshot.get('papers', []) if p.get('id') == data.paper_id), None)
    if sample is None or sample.get('relevant', True) is False:
        raise HTTPException(422, '仅可收录该线索中相关的原始样本文献')
    paper_id, requested_version = canonical_id(data.paper_id)
    if not s.get(Domain, data.domain_id):
        raise HTTPException(404, '目标领域不存在')
    existing = s.scalar(select(ProjectPaperIntake).where(ProjectPaperIntake.project_id == pid,
        ProjectPaperIntake.lead_id == lid, ProjectPaperIntake.paper_id == paper_id,
        ProjectPaperIntake.domain_id == data.domain_id))
    if existing:
        return intake_view(s, existing)
    jobs = list(s.scalars(select(Job).where(Job.kind == 'trend_download').order_by(Job.created.desc())))
    download = next((j for j in jobs if j.payload.get('paper_id') == paper_id
        and j.payload.get('requested_version') == requested_version), None)
    if download is None:
        download = Job(id=uuid.uuid4().hex, kind='trend_download', payload={
            'paper_id': paper_id, 'requested_version': requested_version, 'intake_scope': True},
            result={'intake_explicit': True})
        s.add(download); s.flush()
    intake = ProjectPaperIntake(project_id=pid, lead_id=lid, paper_id=paper_id, domain_id=data.domain_id,
        source_key=lead.source_key, judgment_snapshot={'lead_revision': lead.revision, 'reason': lead.reason,
            'status': lead.status, 'focus_paper_id': lead.snapshot.get('focus_paper_id'), 'sample': sample},
        download_job_id=download.id, status=download.status, analysis_requested=data.analyze,
        analysis_status='pending' if data.analyze else 'not_requested')
    s.add(intake); s.flush()
    if download.status == 'done':
        if verified_result(download):
            apply_download(s, intake, download.result)
        else:
            intake.status = 'failed'
    service.event(s, project, 'paper_intake_requested', {'before': None, 'after': serialize(intake)})
    return intake_view(s, intake)


def verified_result(job):
    result = job.result if isinstance(job.result, dict) else {}
    return verified_file(job.payload.get('paper_id', ''), result.get('version'), result.get('sha256'))


def apply_download(s, intake, result):
    if s.get(Domain, intake.domain_id) is None:
        raise ValueError('目标研究领域已删除，PDF缓存保留，未写入无归属的文献')
    paper = result['paper']
    version = result['version']
    current = s.get(Paper, intake.paper_id)
    allowed = {column.name for column in Paper.__table__.columns} - {'saved', 'read', 'first_seen'}
    metadata = {key: value for key, value in paper.items() if key in allowed}
    metadata.update(id=intake.paper_id, version=version)
    if current is None:
        current = Paper(**metadata); s.add(current); s.flush()
    elif version > current.version:
        for key, value in metadata.items(): setattr(current, key, value)
    if not s.get(Version, (intake.paper_id, version)):
        s.add(Version(paper_id=intake.paper_id, version=version, metadata_json=metadata))
    if not s.get(Membership, (intake.domain_id, intake.paper_id)):
        s.add(Membership(domain_id=intake.domain_id, paper_id=intake.paper_id))
    candidate = research_flow.add_candidate(s, service.project(s, intake.project_id),
        CandidateCreate(paper_id=intake.paper_id, reason=intake.judgment_snapshot['reason']))
    intake.metadata_snapshot = {**metadata, 'pdf_url': result.get('pdf_url'), 'metadata_url': result.get('metadata_url')}
    if 'identity_check' in result:
        intake.metadata_snapshot = {**intake.metadata_snapshot, 'identity_check': result['identity_check']}
    intake.pdf_version, intake.pdf_sha256, intake.pdf_pages = version, result['sha256'], result['pages']
    intake.candidate_id, intake.status = candidate['id'], 'done'
    if intake.analysis_requested:
        queue_analysis(s, intake)


def finish_download(job_id, result, run_token):
    """Runtime publication callback. Requires matching live fenced ownership."""
    with transaction() as s:
        job = s.get(Job, job_id)
        if (not job or job.kind != 'trend_download' or job.status != 'running'
                or not run_token or job.result.get('intake_run_token') != run_token
                or job.result.get('cancel_requested') or job.result.get('pause_requested')
                or (settings(s, 'background_control').get('paused') and not job.result.get('intake_explicit'))):
            raise ValueError('任务已暂停、取消或执行所有权已变化，未发布收录结果')
        paper_id, requested = job.payload['paper_id'], job.payload.get('requested_version')
        metadata_id, metadata_version = canonical_id(result.get('paper', {}).get('id', ''))
        version = result.get('version')
        if (metadata_id != paper_id or type(version) is not int or version < 1
                or result['paper'].get('version') != version or (metadata_version and metadata_version != version)
                or (requested is not None and requested != version)
                or type(result.get('pages')) is not int or not 1 <= result['pages'] <= 1000
                or not verified_file(paper_id, version, result.get('sha256'))):
            raise ValueError('下载结果与固定论文编号、版本或PDF校验不匹配')
        for intake in s.scalars(select(ProjectPaperIntake).where(ProjectPaperIntake.download_job_id == job_id)):
            before = serialize(intake)
            apply_download(s, intake, result)
            record(s, intake, 'paper_intake_downloaded', before)
        job.status, job.progress, job.finished = 'done', 100, now()
        job.result = {**job.result, **result}
        job.message = '论文PDF已收录，原趋势判断与来源保持不变'
        touch(s)
    return True


def analysis_job_allowed(job_id):
    with Session() as s:
        job = s.get(Job, job_id)
        if not job or job.kind != 'analyze' or not job.payload.get('intake_scope'):
            return False, '此任务不属于明确授权的收录分析队列'
        expected = job.payload.get('intake_target')
        rows = list(s.scalars(select(ProjectPaperIntake).where(ProjectPaperIntake.analysis_job_id == job_id)))
        if not expected or not rows or not any(target(s, row) == expected for row in rows):
            return False, '论文、分类或模型身份已变化，未运行另一版本分析'
        blocker = analysis_blocker(s, job_id)
        return not blocker, blocker


def reconcile():
    """Project actual results only; never enqueue, retry or revive any job."""
    with transaction() as s:
        for intake in s.scalars(select(ProjectPaperIntake).where(ProjectPaperIntake.analysis_requested == True)):
            if not intake.pdf_version or not intake.analysis_target:
                continue
            before = serialize(intake)
            expected = target(s, intake)
            analysis = current_analysis(s, intake, expected) if expected == intake.analysis_target else None
            job = s.get(Job, intake.analysis_job_id) if intake.analysis_job_id else None
            if analysis:
                intake.analysis_id, intake.analysis_status, intake.analysis_blocker = analysis.id, 'done', ''
            elif expected != intake.analysis_target:
                intake.analysis_status, intake.analysis_blocker = 'blocked', '目标版本或模型身份已变化，未关联其他分析'
            elif job and job.status in ACTIVE:
                intake.analysis_status = job.status
            elif job and job.status in ('failed', 'done', 'cancelled'):
                intake.analysis_status = 'blocked' if job.result.get('intake_blocker') else 'failed'
                intake.analysis_blocker = job.result.get('intake_blocker') or job.message or '未找到真实当前版本的分析'
            if serialize(intake) != before:
                record(s, intake, 'paper_intake_analysis_reconciled', before)


def retry(s, pid, lid, iid, revision):
    project, lead, intake = get_intake(s, pid, lid, iid, revision)
    job = s.get(Job, intake.download_job_id)
    if not job or not (job.status == 'failed' or (job.status == 'done' and not verified_result(job))):
        raise HTTPException(409, '仅可显式重试失败的下载；暂停任务不会自动恢复')
    before = serialize(intake)
    job.status, job.finished, job.message = 'queued', None, '用户明确重试收录下载'
    job.result = {**{k: v for k, v in job.result.items() if k not in ('intake_run_token', 'pause_requested', 'cancel_requested')}, 'intake_explicit': True}
    intake.status = 'queued'
    record(s, intake, 'paper_intake_retry_requested', before)
    return intake_view(s, intake)


def request_analysis(s, pid, lid, iid, revision):
    project, lead, intake = get_intake(s, pid, lid, iid, revision)
    if not verified_file(intake.paper_id, intake.pdf_version, intake.pdf_sha256):
        raise HTTPException(409, '请先完成并校验PDF收录')
    before = serialize(intake)
    intake.analysis_requested = True
    queue_analysis(s, intake)
    if serialize(intake) != before:
        record(s, intake, 'paper_intake_analysis_requested', before)
    return intake_view(s, intake)


def listing(s, pid, lid):
    get_lead(s, pid, lid)
    return {'items': [intake_view(s, row) for row in s.scalars(select(ProjectPaperIntake)
        .where(ProjectPaperIntake.project_id == pid, ProjectPaperIntake.lead_id == lid)
        .order_by(ProjectPaperIntake.created, ProjectPaperIntake.id))], 'capabilities': capabilities(s)}

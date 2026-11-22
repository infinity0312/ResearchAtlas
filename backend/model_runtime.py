"""Persistent model accounting shared by API, worker and CLI processes.

Reservations are admission-control bounds, never billed-token measurements. We
retain them when a transport outcome or provider usage is unknown. Prompts,
responses, credentials and provider URLs are deliberately absent from this ledger.
Import this module before ``db.init_db`` to register its additive table.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import uuid
import json

from sqlalchemy import Integer, String, case, func, select
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, Session, Setting, now


class ModelBudgetError(RuntimeError):
    """Admission failure, deliberately not a retryable content-validation error."""


class ModelUsage(Base):
    __tablename__ = 'model_usage'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    created: Mapped[str] = mapped_column(String, default=now)
    settled: Mapped[str | None] = mapped_column(String, nullable=True)
    day: Mapped[str] = mapped_column(String, index=True)
    task_id: Mapped[str] = mapped_column(String, index=True)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    paper_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    stage: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default='reserved', index=True)
    reserved_tokens: Mapped[int] = mapped_column(Integer)
    input_allowance: Mapped[int] = mapped_column(Integer)
    output_limit: Mapped[int] = mapped_column(Integer)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)


@dataclass(frozen=True)
class ExecutionContext:
    job_id: str | None = None
    paper_id: str | None = None
    stage: str | None = None
    run_id: str | None = None
    max_calls: int | None = None
    max_tokens: int | None = None


@dataclass(frozen=True)
class Reservation:
    id: str
    day: str
    task_id: str
    reserved_tokens: int


_context: ContextVar[ExecutionContext] = ContextVar('atlas_model_execution', default=ExecutionContext())
BUDGET_KEY = 'model_budget'
BUDGET_DEFAULTS = {'daily_tokens': None, 'task_tokens': None, 'task_calls': None}
ACCOUNTING_TIMEZONE = 'Asia/Shanghai'


def accounting_day(at: datetime | None = None) -> str:
    # Windows often has no IANA tzdata; Shanghai has a stable UTC+8 current day.
    try:
        zone = ZoneInfo(ACCOUNTING_TIMEZONE)
    except ZoneInfoNotFoundError:
        zone = timezone(timedelta(hours=8))
    current = at or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError('Accounting timestamps must include a timezone')
    return current.astimezone(zone).date().isoformat()


def _positive_optional(value, name):
    if value is not None and (type(value) is not int or value <= 0):
        raise ValueError(f'{name} must be a positive integer or null')
    return value


def _identifier(value, name):
    if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 200):
        raise ValueError(f'{name} must be a nonempty string of at most 200 characters')
    return value


@contextmanager
def execution_scope(*, job_id=None, paper_id=None, stage=None, run_id=None,
                    max_calls=None, max_tokens=None):
    """Inherit correlation IDs and tighten, rather than relax, parent budgets."""
    parent = _context.get()
    values = {}
    for field, value in [('job_id', job_id), ('paper_id', paper_id), ('stage', stage), ('run_id', run_id)]:
        values[field] = _identifier(value, field) if value is not None else getattr(parent, field)
    values['run_id'] = values['run_id'] or uuid.uuid4().hex
    for field, value in [('max_calls', max_calls), ('max_tokens', max_tokens)]:
        _positive_optional(value, field)
        existing = getattr(parent, field)
        values[field] = min(existing, value) if existing is not None and value is not None else existing or value
    scope = ExecutionContext(**values)
    token = _context.set(scope)
    try:
        yield scope
    finally:
        _context.reset(token)


def trace_fields() -> dict:
    """Only known correlation fields, safe to add to existing structured events."""
    scope = _context.get()
    return {key: getattr(scope, key) for key in ('job_id', 'paper_id', 'run_id', 'stage')
            if getattr(scope, key) is not None}


def _budget(s) -> dict:
    row = s.get(Setting, BUDGET_KEY)
    saved = row.value if row and isinstance(row.value, dict) else {}
    return {key: _positive_optional(saved.get(key), key) for key in BUDGET_DEFAULTS}


def get_budget() -> dict:
    with Session() as s:
        return {**_budget(s), 'timezone': ACCOUNTING_TIMEZONE}


def _write_lock(s):
    # A deferred SQLite transaction would allow two processes to admit against
    # the same old sum. Acquire the write lock BEFORE reading budgets and usage.
    if s.get_bind().dialect.name != 'sqlite':
        raise RuntimeError('Model usage admission currently requires SQLite')
    s.connection().exec_driver_sql('BEGIN IMMEDIATE')


def set_budget(values: Mapping) -> dict:
    unknown = set(values) - set(BUDGET_DEFAULTS)
    if unknown:
        raise ValueError('Unknown budget fields: ' + ', '.join(sorted(unknown)))
    validated = {key: _positive_optional(value, key) for key, value in values.items()}
    with Session.begin() as s:
        _write_lock(s)
        budget = {**_budget(s), **validated}
        s.merge(Setting(key=BUDGET_KEY, value=budget))
    return {**budget, 'timezone': ACCOUNTING_TIMEZONE}


def _totals(s, *conditions) -> dict:
    pending = ModelUsage.status.in_(['reserved', 'unknown'])
    statement = select(
        func.count(ModelUsage.id),
        func.coalesce(func.sum(case((ModelUsage.status == 'settled', 1), else_=0)), 0),
        func.coalesce(func.sum(case((ModelUsage.status == 'reserved', 1), else_=0)), 0),
        func.coalesce(func.sum(case((ModelUsage.status == 'unknown', 1), else_=0)), 0),
        func.coalesce(func.sum(case((ModelUsage.status == 'nonbillable', 1), else_=0)), 0),
        func.coalesce(func.sum(case((ModelUsage.status == 'settled', ModelUsage.total_tokens), else_=0)), 0),
        func.coalesce(func.sum(case((pending, ModelUsage.reserved_tokens), else_=0)), 0),
    ).where(*conditions)
    keys = ('attempts', 'settled_calls', 'pending_calls', 'unknown_calls', 'nonbillable_calls', 'known_tokens', 'reserved_tokens')
    result = dict(zip(keys, (int(value) for value in s.execute(statement).one())))
    result['committed_tokens'] = result['known_tokens'] + result['reserved_tokens']
    return result


def _tighter(configured, scoped):
    return min(configured, scoped) if configured is not None and scoped is not None else configured or scoped


def _check_tokens(total, limit, reservation_tokens, label):
    if limit is None:
        return
    if total['unknown_calls']:
        raise ModelBudgetError(f'{label}存在未知模型用量，保留额度并暂停后续调用')
    if total['committed_tokens'] + reservation_tokens > limit:
        raise ModelBudgetError(f'{label} token 预算不足；已完成结果和缓存保留')


def reserve(prompt: str, max_output: int, model: str, system_prompt: str = '') -> Reservation:
    """Reserve immediately before one real HTTP attempt, including transport retries.

    UTF-8 byte length plus framing allowance is a deliberately conservative input
    admission estimate for the two text messages. It is never stored as actual
    token usage. Additional-message/tool transports must pass ALL message content.
    """
    if not isinstance(prompt, str) or not isinstance(system_prompt, str):
        raise ValueError('Prompt and system prompt must be strings')
    _positive_optional(max_output, 'max_output')
    if max_output is None:
        raise ValueError('max_output is required')
    _identifier(model, 'model')
    if model is None:
        raise ValueError('model is required')
    scope = _context.get()
    run_id = scope.run_id or uuid.uuid4().hex
    task_id = ('job:' + scope.job_id) if scope.job_id else ('run:' + run_id)
    day = accounting_day()
    input_allowance = len(prompt.encode('utf8')) + len(system_prompt.encode('utf8')) + 128
    reserved_tokens = input_allowance + max_output
    reservation = Reservation(uuid.uuid4().hex, day, task_id, reserved_tokens)
    with Session.begin() as s:
        _write_lock(s)
        budget = _budget(s)
        task = _totals(s, ModelUsage.task_id == task_id)
        calls = _tighter(budget['task_calls'], scope.max_calls)
        if calls is not None and task['attempts'] >= calls:
            raise ModelBudgetError('任务模型调用次数预算已耗尽；已完成结果和缓存保留')
        _check_tokens(task, _tighter(budget['task_tokens'], scope.max_tokens), reserved_tokens, '任务')
        _check_tokens(_totals(s, ModelUsage.day == day), budget['daily_tokens'], reserved_tokens, '每日')
        s.add(ModelUsage(id=reservation.id, day=day, task_id=task_id, job_id=scope.job_id,
                         paper_id=scope.paper_id, run_id=run_id, stage=scope.stage, model=model,
                         reserved_tokens=reserved_tokens, input_allowance=input_allowance,
                         output_limit=max_output))
    return reservation


def reserve_request(body: Mapping) -> Reservation:
    """Account for complete multi-message/tool requests, including reasoning history."""
    content = {'messages': body.get('messages', [])}
    if body.get('tools'):
        content['tools'] = body['tools']
    prompt = json.dumps(content, ensure_ascii=False, separators=(',', ':'))
    return reserve(prompt, body.get('max_tokens'), body.get('model'))


def _usage_counts(usage):
    if not isinstance(usage, Mapping):
        return None
    counts = {key: usage.get(key) for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
    if any(value is not None and (type(value) is not int or value < 0) for value in counts.values()):
        return None
    prompt, completion, total = (counts[key] for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'))
    if total is None:
        if prompt is None or completion is None:
            return None
        counts['total_tokens'] = prompt + completion
    elif prompt is not None and completion is not None and total != prompt + completion:
        return None
    return counts


def settle(reservation: Reservation, usage: Mapping | None = None, status: str = 'success') -> None:
    """Record provider usage before parsing output; retain unknown outcomes safely.

    ``nonbillable`` is for a confirmed rejection with no generated output. A
    timeout after submission is ``unknown``, never a free failure. Settlement is
    idempotent; a terminal record cannot be rewritten by later exception handlers.
    """
    if status not in ('success', 'nonbillable', 'unknown'):
        raise ValueError('Settlement status must be success, nonbillable or unknown')
    counts = _usage_counts(usage) if status == 'success' else None
    with Session.begin() as s:
        _write_lock(s)
        row = s.get(ModelUsage, reservation.id)
        if row is None:
            raise RuntimeError('Unknown model usage reservation')
        if row.status != 'reserved':
            return
        row.settled = now()
        row.status = 'settled' if counts else 'nonbillable' if status == 'nonbillable' else 'unknown'
        if counts:
            for key, value in counts.items():
                setattr(row, key, value)


def usage_summary(*, day: str | None = None, limit: int = 50) -> dict:
    day = day or accounting_day()
    if datetime.strptime(day, '%Y-%m-%d').date().isoformat() != day:
        raise ValueError('day must be YYYY-MM-DD')
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError('limit must be between 1 and 200')
    with Session() as s:
        totals = _totals(s, ModelUsage.day == day)
        rows = s.scalars(select(ModelUsage).where(ModelUsage.day == day)
                         .order_by(ModelUsage.created.desc(), ModelUsage.id.desc()).limit(limit)).all()
        groups = {}
        for key in ('model', 'stage'):
            column = getattr(ModelUsage, key)
            names = s.scalars(select(column).where(ModelUsage.day == day).distinct()).all()
            groups[key] = [{'name': name, **_totals(s, ModelUsage.day == day, column == name)} for name in names]
        public_fields = ('id', 'created', 'settled', 'job_id', 'paper_id', 'run_id', 'stage', 'model',
                         'status', 'reserved_tokens', 'prompt_tokens', 'completion_tokens', 'total_tokens')
        recent = [{key: getattr(row, key) for key in public_fields} for row in rows]
        return {'day': day, 'timezone': ACCOUNTING_TIMEZONE, 'budget': _budget(s),
                'totals': totals, 'by_model': groups['model'], 'by_stage': groups['stage'], 'recent': recent}

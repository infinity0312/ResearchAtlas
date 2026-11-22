from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
import subprocess
import sys
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
import pytest

from backend.db import Session, Setting
from backend.llm_runtime import event, validated, validated_items, reviewed
from backend.model_runtime import (
    ACCOUNTING_TIMEZONE, ModelBudgetError, ModelUsage, accounting_day,
    execution_scope, get_budget, reserve, set_budget, settle, trace_fields, usage_summary,
)
from backend.model_usage import router


def test_nested_scopes_inherit_restore_and_do_not_leak_across_threads():
    assert trace_fields() == {}
    with execution_scope(job_id='job-a', paper_id='paper-a', max_calls=2, max_tokens=500) as outer:
        with execution_scope(stage='review', max_calls=10, max_tokens=1000) as inner:
            assert inner.job_id == 'job-a' and inner.paper_id == 'paper-a'
            assert inner.run_id == outer.run_id
            assert inner.max_calls == 2 and inner.max_tokens == 500
            assert trace_fields()['stage'] == 'review'
        assert 'stage' not in trace_fields()
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(trace_fields).result() == {}
    assert trace_fields() == {}


def test_event_has_trace_but_not_source_or_keys(monkeypatch, tmp_path):
    monkeypatch.setattr('backend.llm_runtime.DATA', tmp_path)
    with execution_scope(job_id='j', paper_id='p', stage='extract', run_id='run'):
        event('cache_hit', task='extract', key='cache-hash', job_id='caller-stale-id')
    logged = json.loads((tmp_path / 'llm-events.jsonl').read_text('utf8'))
    assert {k: logged[k] for k in ('job_id', 'paper_id', 'stage', 'run_id')} == {
        'job_id': 'j', 'paper_id': 'p', 'stage': 'extract', 'run_id': 'run'}
    assert set(logged) == {'time', 'kind', 'job_id', 'paper_id', 'stage', 'run_id', 'task', 'key'}


def test_known_usage_replaces_reservation_without_estimating_actual_tokens():
    with execution_scope(job_id='j', paper_id='p', stage='extract'):
        pending = reserve('source SECRET', 300, 'test', system_prompt='system')
        before = usage_summary()['totals']
        assert before['known_tokens'] == 0
        assert before['reserved_tokens'] == pending.reserved_tokens
        settle(pending, {'prompt_tokens': 23, 'completion_tokens': 8, 'total_tokens': 31})
    summary = usage_summary()
    assert summary['totals']['known_tokens'] == 31
    assert summary['totals']['reserved_tokens'] == 0
    assert summary['recent'][0]['status'] == 'settled'
    assert 'SECRET' not in json.dumps(summary)
    with Session() as s:
        row = s.get(ModelUsage, pending.id)
        assert row.input_allowance == len('source SECRETsystem'.encode('utf8')) + 128
        assert row.paper_id == 'p' and row.stage == 'extract'


@pytest.mark.parametrize('usage', [None, {}, {'prompt_tokens': 10}, {'total_tokens': True},
                                   {'total_tokens': -1}, {'total_tokens': '10'},
                                   {'prompt_tokens': 1, 'completion_tokens': 2, 'total_tokens': 20}])
def test_unknown_usage_holds_reservation_and_blocks_active_daily_budget(usage):
    set_budget({'daily_tokens': 10000})
    pending = reserve('source', 100, 'test')
    settle(pending, usage)
    summary = usage_summary()['totals']
    assert summary['known_tokens'] == 0 and summary['unknown_calls'] == 1
    assert summary['reserved_tokens'] == pending.reserved_tokens
    with pytest.raises(ModelBudgetError, match='未知'):
        reserve('another', 100, 'test')


def test_unknown_task_is_blocked_without_blocking_other_jobs():
    set_budget({'task_tokens': 2000})
    with execution_scope(job_id='j'):
        pending = reserve('source', 100, 'test')
        settle(pending, status='unknown')
    with execution_scope(job_id='j'):
        with pytest.raises(ModelBudgetError, match='未知'):
            reserve('retry', 100, 'test')
    with execution_scope(job_id='different'):
        reserve('unrelated', 100, 'test')


def test_unconfigured_budget_remains_disabled_despite_unknown_outcome():
    assert get_budget() == {'daily_tokens': None, 'task_tokens': None, 'task_calls': None,
                            'timezone': ACCOUNTING_TIMEZONE}
    with execution_scope(job_id='j'):
        pending = reserve('source', 100, 'test')
        settle(pending, status='unknown')
        reserve('next', 100, 'test')
    assert usage_summary()['totals']['attempts'] == 2


def test_confirmed_nonbillable_releases_tokens_but_still_counts_attempt():
    set_budget({'task_calls': 1, 'daily_tokens': 300})
    with execution_scope(job_id='j'):
        pending = reserve('source', 100, 'test')
        settle(pending, status='nonbillable')
        with pytest.raises(ModelBudgetError, match='次数'):
            reserve('retry', 100, 'test')
    totals = usage_summary()['totals']
    assert totals['nonbillable_calls'] == 1
    assert totals['reserved_tokens'] == totals['known_tokens'] == 0
    reserve('different task', 100, 'test')


def test_task_budget_is_shared_by_resumed_job_and_nested_stages():
    set_budget({'task_calls': 2})
    with execution_scope(job_id='j', stage='extract'):
        settle(reserve('first', 10, 'test'), {'total_tokens': 5})
        with execution_scope(stage='repair'):
            settle(reserve('second', 10, 'test'), {'total_tokens': 5})
    with execution_scope(job_id='j', stage='review'):
        with pytest.raises(ModelBudgetError):
            reserve('third', 10, 'test')
    assert usage_summary()['totals']['attempts'] == 2


def test_scoped_token_budget_and_system_prompt_are_admitted_before_reserve():
    with execution_scope(max_tokens=200):
        with pytest.raises(ModelBudgetError):
            reserve('', 50, 'test', system_prompt='s' * 30)
        assert usage_summary()['totals']['attempts'] == 0
        reserve('', 50, 'test', system_prompt='s' * 20)
    assert usage_summary()['totals']['reserved_tokens'] == 198


def test_settlement_is_idempotent_and_cannot_erase_paid_usage():
    pending = reserve('source', 100, 'test')
    settle(pending, {'prompt_tokens': 7, 'completion_tokens': 5})
    settle(pending, status='unknown')
    settle(pending, status='nonbillable')
    totals = usage_summary()['totals']
    assert totals['known_tokens'] == 12 and totals['settled_calls'] == 1


def test_unknown_outcome_cannot_be_released_by_later_exception_handler():
    pending = reserve('source', 100, 'test')
    settle(pending, status='unknown')
    settle(pending, status='nonbillable')
    assert usage_summary()['totals']['unknown_calls'] == 1
    assert usage_summary()['totals']['reserved_tokens'] == pending.reserved_tokens


def test_daily_budget_is_atomic_across_processes():
    # Processes import the isolated test database inherited from tests/conftest;
    # none calls init_db or touches a production profile.
    set_budget({'daily_tokens': 304})  # exactly two 4+128+20 reservations
    script = (
        'from backend.model_runtime import reserve, ModelBudgetError\n'
        'try:\n'
        ' reserve("test",20,"test"); print("admitted")\n'
        'except ModelBudgetError:\n'
        ' print("blocked")\n'
    )
    def child(_):
        result = subprocess.run([sys.executable, '-c', script], cwd=os.getcwd(),
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(child, range(6)))
    assert results.count('admitted') == 2 and results.count('blocked') == 4
    totals = usage_summary()['totals']
    assert totals['attempts'] == 2 and totals['reserved_tokens'] == 304


def test_cache_hits_do_not_reserve_or_bill_and_budget_error_is_not_repaired(monkeypatch, tmp_path):
    monkeypatch.setattr('backend.llm_runtime.DATA', tmp_path)
    class Output(BaseModel):
        value: int
    class Provider:
        config = {'model': 'test'}
        validated_cache = True
        calls = 0
        def generate(self, prompt):
            self.calls += 1
            reservation = reserve(prompt, 100, 'test')
            settle(reservation, {'total_tokens': 17})
            return {'value': 1}
    provider = Provider()
    with execution_scope(job_id='j', max_calls=1):
        assert validated(provider, 'source', Output).value == 1
        assert validated(provider, 'source', Output).value == 1
        with pytest.raises(ModelBudgetError):
            validated(provider, 'new source', Output, attempts=3)
    assert provider.calls == 2  # one successful call and one pre-HTTP rejection
    assert usage_summary()['totals']['attempts'] == 1
    assert usage_summary()['totals']['known_tokens'] == 17


def test_budget_api_validates_preserves_fields_and_has_no_credentials():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    with Session.begin() as s:
        s.merge(Setting(key='llm', value={'key': 'DO-NOT-EXPOSE', 'model': 'private'}))
    assert client.put('/api/model-usage/budget', json={'daily_tokens': 1000, 'task_calls': 5}).status_code == 200
    assert client.put('/api/model-usage/budget', json={'task_calls': None}).json()['daily_tokens'] == 1000
    assert client.get('/api/model-usage/budget').json()['task_calls'] is None
    for body in [{'daily_tokens': 0}, {'task_calls': True}, {'task_tokens': '200'}, {'secret': 'value'}]:
        assert client.put('/api/model-usage/budget', json=body).status_code == 422
    assert client.get('/api/model-usage?day=invalid').status_code == 422
    assert client.get('/api/model-usage?limit=201').status_code == 422
    assert 'DO-NOT-EXPOSE' not in client.get('/api/model-usage').text
    assert 'DO-NOT-EXPOSE' not in client.get('/api/model-usage/budget').text


def test_shanghai_day_and_windows_timezone_fallback(monkeypatch):
    import backend.model_runtime as runtime
    at = datetime(2026, 9, 30, 16, 5, tzinfo=timezone.utc)
    assert accounting_day(at) == '2026-10-01'
    def missing(_):
        raise runtime.ZoneInfoNotFoundError('tzdata missing')
    monkeypatch.setattr(runtime, 'ZoneInfo', missing)
    assert accounting_day(at) == '2026-10-01'


def _streaming_provider(monkeypatch, tmp_path, lines, status=200):
    from backend.study_transport import StudyDeepSeek
    import backend.study_transport as transport
    monkeypatch.setattr('backend.analysis.get_key', lambda: 'test-key-never-log')
    calls = []
    class Response:
        status_code = status
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def iter_lines(self):
            return iter(lines)
    class Client:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def stream(self, *args, **kwargs):
            calls.append(kwargs['json'])
            return Response()
    monkeypatch.setattr(transport.httpx, 'Client', Client)
    provider = StudyDeepSeek(tmp_path / 'calls')
    provider.json_mode('trusted system')
    return provider, calls


@pytest.mark.parametrize('content,finish,exception', [('{"ok":true}', 'stop', None),
                                                      ('{', 'stop', ValueError),
                                                      ('{}', 'length', RuntimeError)])
def test_streaming_records_reported_usage_even_when_output_rejected(monkeypatch, tmp_path, content, finish, exception):
    lines = ['data: ' + json.dumps({'choices': [{'index': 0, 'delta': {'content': content},
                                                'finish_reason': finish}], 'usage': {'total_tokens': 25}}),
             'data: [DONE]']
    provider, calls = _streaming_provider(monkeypatch, tmp_path, lines)
    if exception:
        with pytest.raises(exception):
            provider.generate('source')
    else:
        assert provider.generate('source') == {'ok': True}
    totals = usage_summary()['totals']
    assert len(calls) == 1 and totals['settled_calls'] == 1 and totals['known_tokens'] == 25


def test_streaming_cap_checks_before_post_and_unknown_output_holds_budget(monkeypatch, tmp_path):
    lines = ['data: ' + json.dumps({'choices': [{'index': 0, 'delta': {'content': '{}'}, 'finish_reason': 'stop'}]}),
             'data: [DONE]']
    provider, calls = _streaming_provider(monkeypatch, tmp_path, lines)
    set_budget({'task_tokens': 100000})
    assert provider.generate('source') == {}
    with pytest.raises(ModelBudgetError, match='未知'):
        provider.generate('next')
    assert len(calls) == 1
    assert usage_summary()['totals']['unknown_calls'] == 1


def test_tool_loop_settles_usage_before_missing_choice_error(monkeypatch, tmp_path):
    import backend.study_source_tools as source
    from backend.study_source_tools import run
    class Client:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def post(self, *args, **kwargs):
            return SimpleNamespace(status_code=200, json=lambda: {'usage': {'total_tokens': 39}})
    monkeypatch.setattr(source.httpx, 'Client', Client)
    provider = SimpleNamespace(thinking_enabled=True, system_prompt='system', key='test',
                               config={'base_url': 'https://test'},
                               request_body=lambda prompt: {'model': 'test'})
    with pytest.raises(KeyError):
        run(provider, 'source', {}, tmp_path / 'loop', output_budget=2000)
    assert usage_summary()['totals']['known_tokens'] == 39


def test_multi_message_reservation_includes_reasoning_tools_and_source():
    from backend.model_runtime import reserve_request
    messages = [{'role': 'system', 'content': 'system'}, {'role': 'user', 'content': 'source'},
                {'role': 'assistant', 'reasoning_content': 'continuity' * 100}]
    tools = [{'type': 'function', 'function': {'name': 'read_source'}}]
    body = {'model': 'test', 'max_tokens': 100, 'messages': messages, 'tools': tools}
    reservation = reserve_request(body)
    encoded = json.dumps({'messages': messages, 'tools': tools}, ensure_ascii=False, separators=(',', ':'))
    assert reservation.reserved_tokens == len(encoded.encode('utf8')) + 128 + 100


def _http_provider(monkeypatch, tmp_path, respond):
    import backend.analysis as analysis
    monkeypatch.setattr(analysis, '_circuits', {})
    monkeypatch.setattr(analysis, 'get_key', lambda: 'fake-model-key')
    monkeypatch.setattr(analysis.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr('backend.llm_runtime.DATA', tmp_path)
    calls = []
    def post(*args, **kwargs):
        calls.append(kwargs['json'])
        return respond()
    monkeypatch.setattr(analysis._client, 'post', post)
    return analysis.DeepSeek(), calls


@pytest.mark.parametrize('body', [
    {'usage': {'total_tokens': 27}, 'choices': [{'finish_reason': 'stop', 'message': {'content': '{'}}]},
    {'usage': {'total_tokens': 27}, 'choices': [{'finish_reason': 'length', 'message': {'content': '{}'}}]},
    {'usage': {'total_tokens': 27}, 'choices': []},
])
def test_http_accounts_usage_before_json_truncation_or_missing_choices(monkeypatch, tmp_path, body):
    import httpx
    provider, calls = _http_provider(monkeypatch, tmp_path, lambda: httpx.Response(200, json=body))
    with pytest.raises(ValueError):
        provider.generate('source')
    totals = usage_summary()['totals']
    assert len(calls) == 1 and totals['known_tokens'] == 27 and totals['settled_calls'] == 1
    assert totals['unknown_calls'] == 0


def test_each_429_http_retry_counts_and_cap_prevents_third_post(monkeypatch, tmp_path):
    import httpx
    provider, calls = _http_provider(monkeypatch, tmp_path, lambda: httpx.Response(429))
    set_budget({'task_calls': 2})
    with pytest.raises(ModelBudgetError):
        provider.generate('source')
    assert len(calls) == 2
    totals = usage_summary()['totals']
    assert totals['attempts'] == totals['nonbillable_calls'] == 2
    assert totals['known_tokens'] == totals['reserved_tokens'] == 0


def test_uncertain_http_transport_retry_is_budgeted_before_next_post(monkeypatch, tmp_path):
    import httpx
    def timeout():
        raise httpx.ReadTimeout('unknown submission outcome')
    provider, calls = _http_provider(monkeypatch, tmp_path, timeout)
    set_budget({'task_calls': 1})
    with pytest.raises(ModelBudgetError):
        provider.generate('source')
    totals = usage_summary()['totals']
    assert len(calls) == 1 and totals['unknown_calls'] == 1 and totals['reserved_tokens'] > 0


@pytest.mark.parametrize('operation', ['validated', 'batch', 'reviewed'])
def test_standalone_validation_operations_share_one_task_budget(monkeypatch, tmp_path, operation):
    import httpx
    class Output(BaseModel):
        id: str = 'a'
        value: int
    # reviewed has a valid initial generation; the semantic review is attempt 2.
    raw = {'value': 1} if operation == 'reviewed' else {'id': 'a', 'value': 'invalid'}
    if operation == 'batch':
        raw = {'papers': [raw]}
    body = {'usage': {'total_tokens': 17}, 'choices': [{'finish_reason': 'stop',
                                                     'message': {'content': json.dumps(raw)}}]}
    provider, calls = _http_provider(monkeypatch, tmp_path, lambda: httpx.Response(200, json=body))
    set_budget({'task_calls': 1})
    with pytest.raises(ModelBudgetError):
        if operation == 'validated':
            validated(provider, 'source', Output)
        elif operation == 'batch':
            validated_items(provider, 'source', [{'id': 'a'}], Output, lambda value: None)
        else:
            reviewed(provider, 'source', Output, lambda value: None, 'evidence', 'test review')
    assert len(calls) == 1
    assert usage_summary()['totals']['known_tokens'] == 17

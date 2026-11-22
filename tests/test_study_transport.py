import json
import pytest
from backend.study_transport import consume
from backend.analysis import ModelServiceError


def event(content=None,finish=None,usage=None):
    return 'data: '+json.dumps({'choices':[{'index':0,'delta':{'content':content},'finish_reason':finish}], 'usage':usage})


def test_stream_joins_json_and_records_actual_usage():
    result,text,usage=consume([event('{"answer":'),event('42}'),event(finish='stop',usage={'total_tokens':12}),'data: [DONE]'])
    assert result=={'answer':42} and usage['total_tokens']==12


def test_truncated_or_disconnected_stream_never_accepted():
    for lines in [[event('{"a":1}')], [event('{"a":1}',finish='length'),'data: [DONE]']]:
        with pytest.raises(ModelServiceError,match='Incomplete'):consume(lines)


def test_missing_usage_is_unknown_not_zero_cost():
    assert consume([event('{}',finish='stop'),'data: [DONE]'])[2] is None


def test_literal_newline_preserved_without_rewriting_values():
    value,_,_=consume([event('{"paragraph":"a\nb"}',finish='stop'),'data: [DONE]'])
    assert value['paragraph']=='a\nb'
    with pytest.raises(json.JSONDecodeError):
        consume([event('{"value":',finish='stop'),'data: [DONE]'])


def test_markdown_preserves_math_without_json_escape_interpretation():
    text=r'机制 $\nu + \frac{a}{b} + \theta + \sum_i x_i$ [p4b2]。'
    value,raw,_=consume([event(text,finish='stop'),'data: [DONE]'],output_mode='chapter_markdown',chapter_id=2)
    assert value==dict(id=2,markdown=text,evidence_ids=['p4b2']) and raw==text


def test_markdown_rejects_missing_evidence_and_incomplete_stream():
    with pytest.raises(ValueError,match='cite'):
        consume([event('无依据正文',finish='stop'),'data: [DONE]'],output_mode='chapter_markdown',chapter_id=0)
    with pytest.raises(ModelServiceError,match='Incomplete'):
        consume([event('部分正文 [p1b1]',finish='length'),'data: [DONE]'],output_mode='chapter_markdown',chapter_id=0)


def test_cache_identity_separates_wire_modes():
    from types import SimpleNamespace
    from backend.llm_runtime import identity
    p=SimpleNamespace(config={},output_mode='json',chapter_id=None)
    first=identity(p,'study','prompt',{})
    p.output_mode='chapter_markdown';p.chapter_id=0
    second=identity(p,'study','prompt',{})
    p.chapter_id=1
    assert len({first,second,identity(p,'study','prompt',{})})==3


def test_only_reviewed_fact_aliases_resolve_without_rewriting_prose():
    from backend.study_transport import chapter_value
    value=chapter_value(r'公式 $\nu$ [u1:f2]',1,{'u1:f2':['p4b1','p5b2']})
    assert value['markdown']==r'公式 $\nu$ [p4b1, p5b2]'
    assert value['evidence_ids']==['p4b1','p5b2']
    with pytest.raises(ValueError,match='Unknown reviewed'):
        chapter_value('内容 [u1:f3]',1,{'u1:f2':['p4b1']})


def test_reasoning_stream_is_separate_and_not_parsed_as_answer():
    seen=[]
    thought='data: '+json.dumps({'choices':[{'index':0,'delta':{'reasoning_content':'internal {not json}'}}]})
    value,raw,_=consume([thought,event('{}',finish='stop'),'data: [DONE]'],reasoning=seen.append)
    assert value=={} and raw=='{}' and seen==['internal {not json}']
    with pytest.raises(ModelServiceError,match='Incomplete'):
        consume([thought,event(finish='length'),'data: [DONE]'])


def test_wire_configuration_and_cache_separate_reasoning_budgets():
    from backend.study_transport import StudyDeepSeek
    from backend.llm_runtime import identity
    p=object.__new__(StudyDeepSeek)
    p.config={'model':'test'};p.system_prompt='test';p.output_mode='json';p.max_tokens=1000
    p.temperature=0;p.token_budget=24000;p.thinking_enabled=True;p.reasoning_effort='high'
    body=p.request_body('prompt')
    assert body['thinking']=={'type':'enabled'} and body['reasoning_effort']=='high'
    assert body['max_tokens']==24000 and 'temperature' not in body
    first=identity(p,'study','prompt',{})
    p.reasoning_effort='low'
    assert identity(p,'study','prompt',{})!=first
    p.thinking_enabled=False
    body=p.request_body('prompt')
    assert body['thinking']=={'type':'disabled'} and body['temperature']==0
    assert 'reasoning_effort' not in body

import hashlib
import json

import httpx
import pytest

from backend.db import Analysis, DATA, Session
from backend.product import agentarts_client
from test_product_projects import C, ROOT, create, detail, edit, post, seed


@pytest.fixture
def demo(monkeypatch, tmp_path):
    project = create()
    aid = seed()
    with Session() as s:
        content_hash = s.get(Analysis, aid).content_hash
    parsed = DATA / 'documents' / f'{content_hash}.json'
    scope = tmp_path / 'scope.json'
    scope.write_text(json.dumps({'projects': [project['id']], 'sources': [{
        'analysis_id': aid, 'pdf_sha256': content_hash,
        'parsed_sha256': hashlib.sha256(parsed.read_bytes()).hexdigest(),
    }]}), encoding='utf-8')
    monkeypatch.setenv('ATLAS_AGENTARTS_SCOPE_FILE', str(scope))
    monkeypatch.setenv('ATLAS_AGENTARTS_URL', 'https://demo.example/runtimes/agent-arts-fixture/invocations')
    monkeypatch.setenv('ATLAS_AGENTARTS_KEY', 'test-only')
    return project, '/' + project['id'] + '/agentarts', parsed


def answer(evidence_id='e1'):
    return {'assessments': [{'criterion_id': 'performance', 'findings': [
        {'evidence_id': evidence_id, 'stance': 'supports', 'reason': '这条依据支持同工况比较'},
    ], 'next_step': '复核原页的工况和样本范围'}]}


def test_draft_keeps_authoritative_source_and_binding_is_idempotent(demo, monkeypatch):
    project, path, _ = demo
    calls = []

    def invoke(_runtime, run_id, context):
        calls.append(run_id)
        assert context['sources'] == [{
            'evidence_id': 'e1', 'paper_id': 'product-paper', 'paper_version': 1,
            'title': 'Reviewed model', 'pdf_page': 1, 'quote': 'We propose a verified molecular model.',
        }]
        assert 'owner' not in context
        return answer(), 'execution-fixture'

    monkeypatch.setattr(agentarts_client, 'invoke', invoke)
    assert C.get(ROOT + path).json() == {'enabled': True, 'configured': True, 'review': None}
    response = post(path, {'revision': 1, 'query': 'Reviewed'})
    assert response.status_code == 200, response.text
    draft = response.json()
    assert draft['state'] == 'ready', draft
    assert draft['execution_id'] == 'execution-fixture'
    assert draft['assessments'][0]['status'] == 'supported'
    assert detail(project)['evidence'] == []
    assert C.get(ROOT + path).json()['review']['id'] == draft['id']
    binding_path = f"{path}/{draft['id']}/bind"
    selection = {'revision': 1, 'criterion_id': 'performance', 'evidence_id': 'e1'}
    bound = post(binding_path, selection).json()
    assert bound['expected_revision'] == 2
    assert post(binding_path, selection).json()['bindings'] == bound['bindings']
    evidence = detail(project)['evidence']
    assert len(evidence) == 1 and evidence[0]['snapshot']['quote'] == draft['sources'][0]['quote']
    assert len(calls) == 1


def test_unapproved_projects_and_unmatched_terms_do_not_call_cloud(demo, monkeypatch):
    project, path, _ = demo
    monkeypatch.setattr(agentarts_client, 'invoke', lambda *_: pytest.fail('Must not invoke'))
    other = create()
    assert post('/' + other['id'] + '/agentarts', {'revision': 1, 'query': 'Reviewed'}).status_code == 403
    draft = post(path, {'revision': 1, 'query': 'nonexistentkeyword'}).json()
    assert draft['state'] == 'no_evidence'
    assert draft['execution_id'] is None
    assert draft['assessments'][0]['status'] == 'insufficient'
    assert detail(project)['project']['revision'] == 1


def test_unknown_evidence_is_not_a_review_result(demo, monkeypatch):
    _, path, _ = demo
    monkeypatch.setattr(agentarts_client, 'invoke', lambda *_: (answer('fabricated'), 'execution'))
    response = post(path, {'revision': 1, 'query': 'Reviewed'}).json()
    assert response['state'] == 'failed'
    assert response['assessments'] == []


@pytest.mark.parametrize('change', ['project', 'parsed_source'])
def test_source_or_project_changes_block_adoption(demo, monkeypatch, change):
    project, path, parsed = demo
    monkeypatch.setattr(agentarts_client, 'invoke', lambda *_: (answer(), 'execution'))
    draft = post(path, {'revision': 1, 'query': 'Reviewed'}).json()
    assert draft['state'] == 'ready'
    if change == 'project':
        assert edit(project, constraints='更换工况范围').status_code == 200
    else:
        parsed.write_text('[]', encoding='utf-8')
    revision = detail(project)['project']['revision']
    assert post(f"{path}/{draft['id']}/bind", {
        'revision': revision, 'criterion_id': 'performance', 'evidence_id': 'e1',
    }).status_code == 409
    assert detail(project)['evidence'] == []


def test_workflow_stream_uses_bearer_session_and_final_output(monkeypatch):
    def respond(request):
        assert request.headers['Authorization'] == 'Bearer test-only'
        assert request.headers['x-hw-agentarts-session-id'] == 'review-1'
        assert json.loads(json.loads(request.content)['inputs']['review_context']) == {'criteria': []}
        event = {'event': 'workflow_finished', 'data': {
            'status': {'code': 1, 'desc': 'succeeded'}, 'execution_id': 'trace-1',
            'outputs': {'user_fields': {'review_json': json.dumps(answer())}},
        }}
        return httpx.Response(200, headers={'Content-Type': 'text/event-stream'},
                              text='data: ' + json.dumps(event) + '\n\n')

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(agentarts_client.httpx, 'stream', client.stream)
        result, execution = agentarts_client.invoke(
            agentarts_client.Runtime('https://demo.example/runtimes/agent-arts-test/invocations', 'test-only'),
            'review-1', {'criteria': []},
        )
    assert json.loads(result) == answer()
    assert execution == 'trace-1'
    with pytest.raises(agentarts_client.AgentArtsError, match='未返回工作流结果'):
        agentarts_client.terminal_event(['data: {"event":"message","data":{"text":"partial"}}', ''])

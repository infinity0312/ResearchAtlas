"""Publisher identity and complete-payload rendering checks, without live API calls."""
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from scripts import publish_agent_fulltext as publisher


@pytest.fixture
def publication_packet(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    report = '这是经过原文核查的全文研究报告，解释方法、实验条件与局限。\n' * 60
    source = 'This is a verified passage about the model mechanism.'
    result = {'summary': 'The paper describes a model mechanism.', 'topics': ['topic-one'],
              'methods': ['Model mechanism'], 'problems': [], 'claims': [
                  {'kind': 'method', 'text': 'The model uses this mechanism.',
                   'page': 1, 'quote': source},
              ]}
    draft_path = tmp_path / 'draft.md'
    result_path = tmp_path / 'result.json'
    draft_path.write_text(report, encoding='utf8')
    result_path.write_text(json.dumps({'result': result}), encoding='utf8')
    documents = tmp_path / 'data' / 'documents'
    documents.mkdir(parents=True)
    (documents / 'fixture-source.json').write_text(json.dumps([{'page': 1, 'text': source}]), encoding='utf8')
    packet = {'paper_id': 'fixture-paper', 'work_id': 'fixture-work', 'review_revision': 5,
              'domain_id': 'fixture-domain', 'content_hash': 'fixture-source',
              'reviewed_pages': [1], 'draft_path': str(draft_path), 'result_path': str(result_path)}
    packet_path = tmp_path / 'packet.json'
    packet_path.write_text(json.dumps(packet), encoding='utf8')
    return packet_path, packet, result, report


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


class FakeAtlas:
    def __init__(self, packet, report):
        self.packet = packet
        self.report = report
        self.calls = []
        self.review_revision = packet['review_revision']

    def get(self, path, **kwargs):
        self.calls.append(('GET', path, kwargs))
        if path == '/domains':
            return FakeResponse([{'id': self.packet['domain_id'], 'topics': ['topic-one']}])
        if path == '/paper':
            return FakeResponse({'domain_ids': [self.packet['domain_id']]})
        if path == '/collaboration':
            return FakeResponse([{'id': self.packet['work_id'], 'status': 'review',
                                  'revision': self.review_revision, 'paper_ids': [self.packet['paper_id']],
                                  'markdown': self.report, 'base': 'fixture-fingerprint'}])
        if path == '/collaboration/context':
            return FakeResponse({'fingerprint': 'fixture-fingerprint'})
        raise AssertionError('Unexpected read: ' + path)

    def post(self, path, json):
        self.calls.append(('POST', path, json))
        if path.endswith('/claim'):
            return FakeResponse({'id': self.packet['work_id'], 'revision': self.review_revision + 1,
                                  'lease_token': 'isolated-lease-token'})
        if path.endswith('/publish-analysis'):
            return FakeResponse({'id': self.packet['work_id'], 'status': 'published', 'analysis_id': 77})
        raise AssertionError('Unexpected write: ' + path)


def fake_api(monkeypatch, packet, report):
    atlas = FakeAtlas(packet, report)
    monkeypatch.setattr(publisher.httpx, 'Client', lambda **kwargs: atlas)
    return atlas


@pytest.mark.parametrize('explicit_identity', [False, True])
def test_publication_identity_and_complete_math_payload(publication_packet, monkeypatch, explicit_identity):
    path, packet, original_result, report = publication_packet
    if explicit_identity:
        packet.update(review_owner='actual-legacy-editor', review_model='gpt-6-sol', generation_model='deepseek-flash')
        path.write_text(json.dumps(packet), encoding='utf8')
    atlas = fake_api(monkeypatch, packet, report)
    checked = []

    def check_math(command, **kwargs):
        assert command[-1] == '--analysis'
        checked.append(json.loads(Path(command[2]).read_text('utf8')))
        return SimpleNamespace(returncode=0, stdout='{"formulas":0,"errors":[]}')

    monkeypatch.setattr(publisher.subprocess, 'run', check_math)
    assert publisher.publish(path)['analysis_id'] == 77
    claim = next(c[2] for c in atlas.calls if c[0] == 'POST' and c[1].endswith('/claim'))
    body = next(c[2] for c in atlas.calls if c[0] == 'POST' and c[1].endswith('/publish-analysis'))
    assert claim['owner'] == ('actual-legacy-editor' if explicit_identity else 'codex-editor')
    assert body['review_model'] == ('gpt-6-sol' if explicit_identity else 'codex')
    assert body['revision'] == packet['review_revision'] + 1
    assert checked[0]['result'] == {**body['result'], 'fulltext_markdown': body['fulltext_markdown']}
    assert json.loads(Path(packet['result_path']).read_text('utf8')) == {'result': original_result}
    if explicit_identity:
        assert body['generation_model'] == 'deepseek-flash'
    else:
        assert 'generation_model' not in body


@pytest.mark.parametrize('field', ['summary', 'claims', 'fulltext_markdown'])
def test_actual_structured_math_failure_blocks_api_access(publication_packet, monkeypatch, field):
    path, packet, result, report = publication_packet
    invalid = 'Invalid $\\notarealcommand{x}$ formula.'
    if field == 'fulltext_markdown':
        report += invalid
        Path(packet['draft_path']).write_text(report, encoding='utf8')
    elif field == 'claims':
        result['claims'][0]['text'] = invalid
    else:
        result[field] = invalid
    Path(packet['result_path']).write_text(json.dumps(result), encoding='utf8')
    atlas = fake_api(monkeypatch, packet, report)
    node = shutil.which('node') or 'F:/dev/node/node.exe'
    if not Path(node).exists():
        pytest.skip('Node runtime unavailable')
    real_run = publisher.subprocess.run
    validator = Path(publisher.__file__).parent / 'validate_fulltext_math.mjs'

    def actual_math(command, **kwargs):
        return real_run([node, str(validator), command[2], '--analysis'], **kwargs)

    monkeypatch.setattr(publisher.subprocess, 'run', actual_math)
    with pytest.raises(ValueError, match='Math rendering validation failed'):
        publisher.publish(path)
    assert atlas.calls == []
    assert not path.with_suffix('.lease.json').exists()


def test_revision_conflict_still_prevents_claim_and_publication(publication_packet, monkeypatch):
    path, packet, result, report = publication_packet
    atlas = fake_api(monkeypatch, packet, report)
    atlas.review_revision += 1
    monkeypatch.setattr(publisher.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout='{}'))
    with pytest.raises(ValueError, match='Review revision changed'):
        publisher.publish(path)
    assert not any(c[0] == 'POST' for c in atlas.calls)
    assert not path.with_suffix('.lease.json').exists()

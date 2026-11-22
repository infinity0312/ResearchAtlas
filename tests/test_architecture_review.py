"""Independent regressions for malformed history and repeated source corrections."""
import hashlib
import json
import uuid

import pytest
from sqlalchemy import delete

from backend.db import Analysis, DATA, Domain, Paper, Session, Setting, now
from backend import workspace
from backend.analysis_repository import (
    AnalysisConflict, assert_current, read_analysis, source_updates,
)
from backend.evidence_contracts import valid_grounding


@pytest.mark.parametrize('identifier', [[], {}, None, 7, ' '])
def test_malformed_historical_claim_ids_fail_validation_without_crashing(identifier):
    result = {'claims': [{'id': identifier}], 'grounding': {
        'summary': [{'text': 'summary', 'claim_ids': ['c_valid']}],
        'topics': [], 'methods': [], 'problems': [],
    }, 'summary': 'summary', 'topics': [], 'methods': [], 'problems': []}
    assert valid_grounding(result) is False


def test_blank_bound_summary_is_not_verified():
    result = {'claims': [{'id': 'c_valid'}], 'grounding': {
        'summary': [{'text': '', 'claim_ids': ['c_valid']}],
        'topics': [], 'methods': [], 'problems': [],
    }, 'summary': '', 'topics': [], 'methods': [], 'problems': []}
    assert valid_grounding(result) is False


def test_multiple_source_corrections_keep_old_analysis_stale_and_block_publication():
    pid = 'review-source-' + uuid.uuid4().hex
    folder = DATA / 'documents'
    folder.mkdir(exist_ok=True)
    pdf = folder / (hashlib.sha256(pid.encode()).hexdigest() + 'v1.pdf')
    pdf.write_bytes(b'isolated source history fixture; not parsed as PDF')
    original = hashlib.sha256(pdf.read_bytes()).hexdigest()
    source_text = json.dumps([{'page': 1, 'text': 'Original fixture narrative passage.'}])
    (folder / (original + '.json')).write_text(source_text, encoding='utf8')
    with Session.begin() as s:
        s.add(Paper(id=pid, title=pid, abstract='fixture', published=now(), updated=now()))
        s.add(Analysis(paper_id=pid, domain_id='molecules', version=1, taxonomy_version=1,
                       model='fixture', content_hash=original, result={}))
    workspace.sync()

    def revise(number):
        with Session() as s:
            entry = s.get(Setting, 'workspace-index').value['source:' + pid]
        target = workspace.local_path(entry['path'])
        text = json.dumps([{'page': 1, 'text': f'Corrected fixture narrative revision {number}.'}])
        target.write_text(text, encoding='utf8')
        report = workspace.sync()
        assert not any(c.get('resource') == 'source:' + pid for c in report['conflicts'])
        with Session() as s:
            return s.get(Setting, 'source-edit:' + original).value['digest']

    first_digest = revise(1)
    with Session.begin() as s:
        first_analysis = Analysis(paper_id=pid, domain_id='molecules', version=1,
                                  taxonomy_version=1, model='fixture',
                                  content_hash=first_digest, result={})
        s.add(first_analysis)
    # Adopt the newest analysis into the editable mirror, then correct it twice.
    workspace.sync()
    revise(2)
    current_digest = revise(3)
    assert current_digest != first_digest
    with Session() as s:
        paper = s.get(Paper, pid)
        domain = s.get(Domain, 'molecules')
        analysis = s.get(Analysis, first_analysis.id)
        quality = read_analysis(analysis, paper, domain, source_updates(s))['quality']
        assert quality['freshness'] == 'stale'
        with pytest.raises(AnalysisConflict, match='解析来源已修订'):
            assert_current(s, paper, domain, first_digest)
        assert analysis.content_hash == first_digest
        assert source_updates(s, []) == {}
        assert not source_updates(s, ['a-different-paper']).current_by_paper
    # Simulate an existing library corrected before redirect history was added.
    # The current PDF selects the canonical source even for an older derived hash.
    with Session.begin() as s:
        s.execute(delete(Setting).where(Setting.key.like('source-redirect:%'),
                                       Setting.value['paper_id'].as_string() == pid))
    with Session() as s:
        paper = s.get(Paper, pid)
        domain = s.get(Domain, 'molecules')
        analysis = s.get(Analysis, first_analysis.id)
        updates = source_updates(s, [pid])
        assert updates.current_by_paper[(pid, 1)] == current_digest
        assert read_analysis(analysis, paper, domain, updates)['quality']['freshness'] == 'stale'
        with pytest.raises(AnalysisConflict, match='解析来源已修订'):
            assert_current(s, paper, domain, first_digest)


def test_missing_pdf_does_not_assign_old_source_edit_to_new_paper_version():
    pid = 'review-version-' + uuid.uuid4().hex
    with Session.begin() as s:
        s.add(Paper(id=pid, version=2, title=pid, abstract='fixture', published=now(), updated=now()))
        s.add(Setting(key='source-edit:old-version-hash', value={
            'paper_id': pid, 'paper_version': 1, 'digest': 'corrected-old-version-hash',
        }))
    with Session() as s:
        assert source_updates(s, [pid]).current_by_paper == {}


def test_publication_guard_keeps_expected_version_when_refreshing_same_session():
    pid = 'review-alias-' + uuid.uuid4().hex
    with Session.begin() as s:
        s.add(Paper(id=pid, version=1, title=pid, abstract='fixture', published=now(), updated=now()))
    with Session() as reader:
        paper = reader.get(Paper, pid)
        domain = reader.get(Domain, 'molecules')
        with Session.begin() as writer:
            writer.get(Paper, pid).version = 2
        with pytest.raises(AnalysisConflict, match='论文或分类版本已变化'):
            assert_current(reader, paper, domain, 'source-fixture')

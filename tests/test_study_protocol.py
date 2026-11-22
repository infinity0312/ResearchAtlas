import pytest
from backend.study_protocol import evidence_context, checkpoint, batch_readiness


def test_cross_page_context_and_no_silent_truncation():
    blocks = {f'p{i}': {'page': i, 'text': 'evidence'} for i in range(1, 9)}
    got = evidence_context(blocks, ['p4'], explicit_pages=[7])
    assert set(got) == {'p3', 'p4', 'p5', 'p6', 'p7', 'p8'}
    with pytest.raises(ValueError, match='unavailable'):
        evidence_context(blocks, ['p4'], explicit_pages=[20])
    with pytest.raises(ValueError, match='split'):
        evidence_context(blocks, ['p4'], max_chars=1)


def test_checkpoints_preserve_previous_evidence(tmp_path):
    p = tmp_path/'stage.json'
    checkpoint(p, {'value': 1}); checkpoint(p, {'value': 1})
    with pytest.raises(ValueError, match='conflict'):
        checkpoint(p, {'value': 2})
    assert '1' in p.read_text()


def test_batch_refuses_stale_or_changed_or_unreviewed_reports():
    m = dict(frozen_fingerprint='v2', development_paper_ids=['dev'], heldout_paper_ids=['a','b','c'])
    rows = [dict(paper_id=p, fingerprint='v2', report_sha256='hash', editorial_report_sha256='hash',
                 editorial_passed=True, blocking_errors=0, core_omissions=0, repair_cycles=1,
                 usage_complete=True,editorial_content_changes=0) for p in m['heldout_paper_ids']]
    assert batch_readiness(m, rows)['batch_allowed']
    for field, value in [('fingerprint','v1'), ('report_sha256','changed'),
                         ('editorial_passed',False), ('blocking_errors',1), ('usage_complete',False),
                         ('editorial_content_changes',1)]:
        edited=[dict(r) for r in rows]; edited[0][field]=value
        assert not batch_readiness(m, edited)['batch_allowed']
    assert not batch_readiness(m, rows[:-1])['batch_allowed']
    m['heldout_paper_ids'][0]='dev'
    assert not batch_readiness(m, rows)['batch_allowed']

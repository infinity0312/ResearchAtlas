from backend.study_protocol import consecutive_readiness


def fixtures(n=12):
    ids=[str(i) for i in range(n)]
    manifest={'ordered_paper_ids':ids,'frozen_fingerprint':'v'}
    rows=[dict(paper_id=i,fingerprint='v',status='passed',editorial_passed=True,report_sha256=i+'hash',editorial_report_sha256=i+'hash',source_complete=True,math_passed=True,blocking_errors=0,core_omissions=0,editorial_content_changes=0,usage_complete=True,repair_cycles=0) for i in ids]
    return manifest,rows


def test_requires_ten_and_resets_at_failure():
    m,r=fixtures()
    assert not consecutive_readiness(m,r[:9])['batch_allowed']
    assert consecutive_readiness(m,r[:10])['batch_allowed']
    r[3]['status']='failed'
    assert consecutive_readiness(m,r)['consecutive_passes']==8


def test_no_skips_version_changes_or_editor_rewrites():
    m,r=fixtures()
    assert not consecutive_readiness(m,r[1:])['batch_allowed']
    r[0]['fingerprint']='other'
    assert consecutive_readiness(m,r)['consecutive_passes']==0
    r[0]['fingerprint']='v';r[-1]['editorial_content_changes']=1
    assert consecutive_readiness(m,r)['consecutive_passes']==0

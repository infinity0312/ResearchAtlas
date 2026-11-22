import pytest
from backend.fulltext_pipeline import FullDraft, Patch, Issue, Audit, Adjudication, apply_patch, validate_draft, render, run
from backend.llm_runtime import identity
from types import SimpleNamespace


def draft():
    return FullDraft(summary='summary '*10,topics=['T'],methods=['M'],claims=[
        dict(kind=k,text='Fact',evidence_id='p1b1') for k in ['method','contribution','limitation','method','method','method','method','method']],
        chapters=[dict(id=i,markdown='source-based explanation '*40,evidence_ids=['p1b1']) for i in range(5)])


def test_repairs_cannot_overwrite_unrequested_content():
    d=draft();p=Patch(replacements=[dict(field='summary',value='revised '*10)])
    revised=apply_patch(d,p,{'summary'})
    assert revised.chapters==d.chapters and revised.claims==d.claims
    with pytest.raises(ValueError,match='Unrequested'):apply_patch(d,p,{'methods'})
    with pytest.raises(ValueError,match='every requested'):apply_patch(d,p,{'summary','methods'})


def test_chapters_and_evidence_are_complete_not_just_long():
    d=draft();validate_draft(d,{'p1b1':{'page':1,'text':'A complete source statement.'}},['T'])
    assert render(d).count('## ')==5
    d.chapters[4].id=3
    with pytest.raises(ValueError,match='exactly once'):validate_draft(d,{'p1b1':{'page':1,'text':'A complete source statement.'}},['T'])
    d=draft();d.claims[0].evidence_id='fabricated'
    with pytest.raises(ValueError,match='unknown'):validate_draft(d,{'p1b1':{'page':1,'text':'A complete source statement.'}},['T'])


def test_cache_separates_system_prompt_and_output_budget():
    p=SimpleNamespace(config={'model':'m'},system_prompt='A',max_tokens=1000)
    a=identity(p,'t','prompt',{})
    p.system_prompt='B';b=identity(p,'t','prompt',{})
    p.max_tokens=2000;c=identity(p,'t','prompt',{})
    assert len({a,b,c})==3


def test_safe_body_alias_is_not_an_arbitrary_path():
    i=Issue(field='chapters.1.markdown',draft_fragment_id='d0',reason='specific defect',evidence_ids=['p1b1'],correction='source correction')
    assert i.field=='chapters.1'
    with pytest.raises(ValueError):
        apply_patch(draft(),Patch(replacements=[dict(field='chapters.9.markdown',value='x')]),{'chapters.9.markdown'})


def test_model_pass_still_requires_editor_and_false_criticism_is_not_applied(monkeypatch,tmp_path):
    calls=[]
    def generate(provider,prompt,schema,check=lambda _:None,task='',**kwargs):
        calls.append(task)
        if schema is FullDraft:v=draft()
        elif schema is Audit:v=Audit(issues=[Issue(field='summary',draft_fragment_id='d0',reason='a proposed defect',evidence_ids=['p1b1'],correction='change summary')] if '"field":"summary"' in prompt else [])
        elif schema is Adjudication:v=Adjudication(verdicts=[dict(index=0,confirmed=False,reason='The source and draft agree; criticism is false.')])
        else:raise AssertionError('A false criticism must not trigger repair')
        check(v);return v
    monkeypatch.setattr('backend.fulltext_pipeline.validated',generate)
    state=run(SimpleNamespace(config={'model':'fake'}),[dict(page=1,text='source evidence '*60)],['T'],tmp_path,'skill')
    assert state['status']=='awaiting_editorial_review' and not state['published']
    assert not list(tmp_path.glob('patch-*.json'))

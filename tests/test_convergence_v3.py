import pytest
import json
from types import SimpleNamespace
from backend.convergence_v3 import Audit, Patch, checked_audit, patch_targets, acceptance_gate, CHECKS
from backend.study_protocol import digest


def test_audit_cannot_silently_skip_coverage_or_regression():
    rows=[dict(category=k,status='checked',rationale='Source-specific completed inspection') for k in CHECKS]
    a=Audit(checks=rows,findings=[])
    checked_audit(a,{'p':'text'},{'p1b1':{}},True)
    a.checks[-1].status='not_applicable'
    with pytest.raises(ValueError,match='regression'):checked_audit(a,{'p':'text'},{'p1b1':{}},True)
    a.checks=a.checks[:-1]
    with pytest.raises(ValueError,match='exactly once'):checked_audit(a,{}, {},False)


def test_local_patch_rejects_stale_and_unrelated_changes():
    old={'c0p0':'bad','c0p1':'verified','metadata':{'summary':'good'}}
    p=Patch(edits=[dict(target='c0p0',old_sha256=digest('bad'),value='fixed')])
    new=patch_targets(old,p,{'c0p0'})
    assert old['c0p0']=='bad' and new['c0p1']==old['c0p1'] and new['metadata']==old['metadata']
    p.edits[0].old_sha256='wrong'
    with pytest.raises(ValueError,match='Stale'):patch_targets(old,p,{'c0p0'})
    with pytest.raises(ValueError,match='Unrequested'):patch_targets(old,p,{'c0p1'})


def fixtures():
    m=dict(target=15,fingerprint='v',ordered_paper_ids=[str(i) for i in range(16)],development_paper_ids=['dev'])
    rows=[dict(paper_id=str(i),fingerprint='v',status='passed',independent_review=True,autonomous_model_audit=True,
        human_content_feedback=False,report_sha256='r',reviewed_sha256='r',source_complete=True,math_passed=True,
        style_passed=True,blocking_errors=0,core_omissions=0,usage_complete=True,repair_rounds=1,editorial_content_changes=0) for i in range(16)]
    return m,rows


def test_fifteen_gate_is_consecutive_source_bound_and_independent():
    m,r=fixtures()
    assert not acceptance_gate(m,r[:14],'v')['batch_allowed']
    assert acceptance_gate(m,r[:15],'v')['batch_allowed']
    r[8]['status']='failed'
    assert acceptance_gate(m,r,'v')['consecutive_passes']==7
    assert not acceptance_gate(m,r,'new')['batch_allowed']
    assert not acceptance_gate(m,r[1:],'v')['batch_allowed']


@pytest.mark.parametrize('field,value',[('style_passed',False),('human_content_feedback',True),('autonomous_model_audit',False),
    ('reviewed_sha256','stale'),('usage_complete',False),('source_complete',False),('repair_rounds',3),('independent_review',False)])
def test_no_bulk_on_weak_evidence(field,value):
    m,r=fixtures();r[1][field]=value
    assert not acceptance_gate(m,r[:15],'v')['batch_allowed']


class FakeProvider:
    config={'model':'fake'}
    last_usage={'total_tokens':30}
    def __init__(self, needs_source=False):
        self.calls=[];self.needs_source=needs_source
    def json_mode(self,system):pass
    def generate(self,prompt):
        self.calls.append(prompt)
        if prompt.startswith('Extract central'):
            return dict(pages=[dict(page=1,role='method',content='A central method and evaluation.',source_problem='')],
                facts=[dict(kind='method',statement='A complete central source method.',evidence_ids=['p1b1'],
                    condition='Specific source conditions.',needs_visual_review=False)],open_questions=[])
        if prompt.startswith('Verify only audit category'):
            inputs=json.loads(prompt.split('\nINPUT:\n')[1]);category=inputs['category']
            issues=[]
            if self.needs_source and category=='coverage':issues=[dict(target=next(iter(inputs['targets'])),evidence_ids=['p1b1'],reason='Critical figure values are not readable.',close_when='Supply verified original figure values.',severity='needs_source')]
            return dict(check=dict(category=category,status='checked',rationale='Specific original text inspected.'),findings=issues)
        if prompt.startswith('Act as a source-bound'):
            inputs=json.loads(prompt.split('\nINPUT:\n')[1])
            issues=[]
            if self.needs_source:
                issues=[dict(target=next(iter(inputs['targets'])),evidence_ids=['p1b1'],
                    reason='Critical figure values are not readable.',close_when='Supply verified original figure values.',severity='needs_source')]
            return dict(checks=[dict(category=k,status='checked',rationale='Specific original text inspected.') for k in CHECKS],findings=issues)
        if prompt.startswith('Independently assess prose'):
            inputs=json.loads(prompt.split('\nINPUT:\n')[1])
            return dict(checks=[dict(category=k,passed=True,rationale='Continuous specific scientific prose preserved.',targets=[next(iter(inputs['paragraphs']))]) for k in ['continuity','emphasis','granularity','integration','preservation']])
        if prompt.startswith('Write Chinese metadata'):
            return dict(summary='Scientific source summary '*5,topics=['T'],methods=['M'],problems=[],
                claims=[dict(kind=k,basis='author',text='Source statement',evidence_id='p1b1') for k in
                    ['method','contribution','limitation','method','method','method','method','method']])
        if prompt.startswith('Write only this scholarly'):
            return dict(paragraphs=['Mechanism with evidence [p1b1]. '*25,'Limitations with evidence [p1b1]. '*25])
        if prompt.startswith('Independently assess'):
            return dict(verdicts=[dict(index=0,outcome='needs_source',evidence_ids=['p1b1'],reason='Original figure is still unavailable.')])
        raise AssertionError('Unexpected paid stage')


def test_actual_runner_audits_inventory_every_chapter_and_metadata(tmp_path,monkeypatch):
    from backend.convergence_v3 import Runner
    monkeypatch.setattr('backend.convergence_v3.subprocess.run',lambda *a,**k:SimpleNamespace(returncode=0,stdout='{"errors":[],"formulas":0}'))
    p=FakeProvider();runner=Runner(p,tmp_path)
    state=runner.run([dict(page=1,text='Source method and limitations. '*20)],['T'])
    assert state['status']=='awaiting_independent_review' and state['published'] is False
    assert sum(c.startswith('Verify only audit category') for c in p.calls)==42
    assert len(list(tmp_path.glob('*.usage.json')))==len(p.calls)
    count=len(p.calls)
    Runner(p,tmp_path).run([dict(page=1,text='Source method and limitations. '*20)],['T'])
    assert len(p.calls)==count


def test_visual_gap_blocks_generation_and_repair_without_hiding_cost(tmp_path):
    from backend.convergence_v3 import Runner
    p=FakeProvider(needs_source=True)
    with pytest.raises(ValueError,match='needs_source'):
        Runner(p,tmp_path).run([dict(page=1,text='Source method and limitations. '*20)],['T'])
    assert len(p.calls)==8 and not (tmp_path/'candidate.json').exists()

def test_resume_ignores_nested_object_insertion_order(tmp_path):
    from backend.convergence_v3 import Runner, Audit
    provider=FakeProvider()
    runner=Runner(provider,tmp_path)
    a={'targets':{'inventory':{'b':2,'a':1}},'source':{}}
    b={'source':{},'targets':{'inventory':{'a':1,'b':2}}}
    first=runner.ask('stable','Act as a source-bound',a,Audit)
    second=Runner(provider,tmp_path).ask('stable','Act as a source-bound',b,Audit)
    assert first==second and len(provider.calls)==1


def test_completed_invalid_schema_gets_one_bounded_repair(tmp_path):
    from backend.convergence_v3 import Runner, Paragraphs
    class Provider(FakeProvider):
        def generate(self,prompt):
            self.calls.append(prompt)
            if prompt.startswith('Repair only the listed'):return {'paragraphs':['Preserved source fact A.','Preserved source fact B.']}
            return {'paragraphs':'invalid list'}
    provider=Provider();value=Runner(provider,tmp_path).ask('schema','Generate',{},Paragraphs)
    assert len(value.paragraphs)==2 and len(provider.calls)==2
    assert (tmp_path/'schema.raw.json').exists() and (tmp_path/'schema-schema-repair.usage.json').exists()

def test_schema_repair_does_not_loop_forever(tmp_path):
    from backend.convergence_v3 import Runner, Paragraphs
    class Provider(FakeProvider):
        def generate(self,prompt):self.calls.append(prompt);return {'paragraphs':'invalid'}
    provider=Provider()
    with pytest.raises(ValueError):Runner(provider,tmp_path).ask('schema','Generate',{},Paragraphs)
    assert len(provider.calls)==2

def test_target_binding_error_gets_bounded_repair(tmp_path):
    from backend.convergence_v3 import Runner, AuditPart
    class Provider(FakeProvider):
        def generate(self,prompt):
            self.calls.append(prompt)
            target='inventory' if prompt.startswith('Repair only the listed') else 'facts'
            return dict(check=dict(category='attribution',status='checked',rationale='Specific source attribution checked.'),findings=[dict(target=target,evidence_ids=['p1b1'],severity='blocking',reason='Provided evidence citation is missing.',close_when='Add the supplied supporting evidence.')])
    def check(value):
        if any(f.target!='inventory' for f in value.findings):raise ValueError('Unbound finding; target must be inventory')
    p=Provider();value=Runner(p,tmp_path).ask('bound','Verify',{'targets':{'inventory':{}}},AuditPart,check)
    assert value.findings[0].target=='inventory' and len(p.calls)==2

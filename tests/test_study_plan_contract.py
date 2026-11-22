import copy
import pytest
from test_study_compiler import sample
from backend.study_plan_contract import canonical_plan,plan_diagnostics,candidate_plan,load_plan_input
from backend.study_protocol import checkpoint


def test_known_fact_alias_expands_all_sources_and_deduplicates_without_rewriting():
    p,f,b,_=sample();raw=p.model_dump();b['p2b1']={'page':2,'text':'Complete table header and denominator evidence.'}
    f['f0']['evidence_ids']=['p1b1','p2b1'];raw['claims'][0]['evidence_id']='f0'
    raw['claims'][0]['context_evidence_ids']=['p1b1','p2b1'];raw['results'][0]['evidence_ids']=['f0','p1b1']
    before=copy.deepcopy(raw);v,changes=canonical_plan(raw,f,b)
    assert raw==before and changes
    assert v['claims'][0]['evidence_id']=='p1b1' and v['claims'][0]['context_evidence_ids']==['p2b1']
    assert v['results'][0]['evidence_ids']==['p1b1','p2b1']
    assert v['results'][0]['value']==raw['results'][0]['value']
    assert v['claims'][0]['text']==raw['claims'][0]['text']
    candidate_plan(raw,f,b,['主题'])


def test_diagnostics_expose_schema_sources_topics_and_ownership_together():
    p,f,b,_=sample();raw=p.model_dump();raw['results'][0]['value']='0.08 ± 0.01'
    raw['formulas'][0]['evidence_ids']=['p99b9'];raw['topics']=['不存在'];raw['units'][5]['result_ids']=['r1']
    errors=plan_diagnostics(raw,f,b,['主题']);text=str(errors)
    assert 'results.0.value' in text and 'p99b9' in text and '不存在' in text and 'one owner' in text


def test_unknown_alias_is_never_guessed():
    p,f,b,_=sample();raw=p.model_dump();raw['claims'][0]['evidence_id']='u99:f99'
    with pytest.raises(ValueError,match='u99:f99'):candidate_plan(raw,f,b,['主题'])


def test_redundant_owner_removed_only_when_consistent():
    p,f,b,_=sample();raw=p.model_dump();raw['results'][0]['unit_id']='s4'
    v,changes=canonical_plan(raw,f,b);assert 'unit_id' not in v['results'][0] and changes
    raw['results'][0]['unit_id']='s1'
    with pytest.raises(ValueError,match='unit_id'):candidate_plan(raw,f,b,['主题'])


def test_failed_candidate_is_repairable_without_rendering_or_manual_rewrite(tmp_path):
    p,f,b,_=sample();raw=p.model_dump();raw['results'][0]['value']='two values'
    with pytest.raises(ValueError):candidate_plan(raw,f,b,['主题'],tmp_path)
    recovered=load_plan_input(tmp_path).model_dump()
    assert recovered['results'][0]['value']=='two values'
    assert not (tmp_path/'plan.json').exists()


@pytest.mark.parametrize('raw',[None,[],{'units':None,'results':[{'id':'r1','unit_id':'s1'}]}, {'units':[{'fact_ids':[{},None],'chapter':[]}]}])
def test_malformed_payloads_produce_diagnostics_not_unhandled_type_errors(raw):
    _,f,b,_=sample();v,_=canonical_plan(raw,f,b)
    assert plan_diagnostics(v,f,b,['主题'])


def test_short_valid_chinese_scope_and_finite_scalar_contract():
    p,f,b,_=sample();raw=p.model_dump();raw['invariants'][0]['scope']='全报告'
    candidate_plan(raw,f,b,['主题'])
    for bad in ['83±0.7','a=83','NaN','83/84']:
        raw['results'][0]['value']=bad
        with pytest.raises(ValueError):candidate_plan(raw,f,b,['主题'])

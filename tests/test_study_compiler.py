import copy
from types import SimpleNamespace
import pytest
from backend.study_compiler import (Plan, Result, Explanations, Explanation, check_plan,
    approve_plan, compare_results, check_explanations, compile_report, explain)
from backend.study_protocol import digest


def sample():
    blocks={'p1b1':{'page':1,'text':'Original scientific evidence sentence with complete context and experimental conditions.'}}
    facts={f'f{i}':{'id':f'f{i}','statement':'该研究在所报告的受控实验条件下验证方法，同时保留原文明确的适用范围。'*8,
                   'condition':'独立测试集，不表示跨任务或因果结论。','evidence_ids':['p1b1']} for i in range(10)}
    units=[dict(id=f's{i}',chapter=i//2,title='科学内容单元',fact_ids=[f'f{i}'],responsibility='必须覆盖该单元原文中的科学机制与适用条件。',result_ids=['r1','r2'] if i==4 else [],formula_ids=['e1'] if i==2 else []) for i in range(10)]
    cell=dict(experiment='test',model='model',train_n='1000',supervision='joint',split='heldout',protocol='single',metric='MAE',unit='kcal/mol',statistic='mean',evidence_ids=['p1b1'])
    p=Plan(summary='本文通过受控实验研究新方法的机制、结果、边界和复现条件，不将观察直接推广到所有数据。',topics=['主题'],methods=['方法'],problems=['问题'],
        claims=[dict(kind=['method','contribution','limitation'][i%3],basis='author',text='该方法在原文受控条件下得到支持。',evidence_id='p1b1') for i in range(8)],
        units=units,results=[dict(id='r1',value='0.08',**cell),dict(id='r2',value='0.07',**{**cell,'train_n':'50000','supervision':'energy'})],
        formulas=[dict(id='e1',label='目标函数',latex=r'L=\sum_i e_i^2',symbols_and_scope='这里的误差项按原文规定的样本范围求和，不能外推。',evidence_ids=['p1b1'])],
        invariants=[dict(key='scope',scope='仅限该测试数据集',statement='不能将该数据集结果当作普遍因果结论。',evidence_ids=['p1b1']),dict(key='supervision',scope='区分联合与仅能量训练',statement='不能将不同训练规模的数值当作同条件比较。',evidence_ids=['p1b1'])],formula_applicability='原文包含明确训练目标，必须完整呈现。')
    v=Explanations(units=[Explanation(unit_id=u.id,text='这一机制通过改变信息传递方式，使模型能利用原先无法直接比较的局部证据。结论仅适用于上述实验条件；它支持方法在该任务上的有效性，不能证明机制对所有数据都是必要条件。原文中的负面结果和训练条件应与主要结果一起考虑，才能判断适用边界。') for u in p.units])
    return p,facts,blocks,v


def approval(p,f,b):
    return dict(plan_sha256=digest(p.model_dump()),facts_sha256=digest(f),source_blocks_sha256=digest(b),reviewer_kind='codex',reviewer='editor',status='approved',blocking_issues=[],required_unit_ids=[u.id for u in p.units],
        **{k:'checked' for k in ['formula_coverage','negative_results','reproduction','result_conditions','cross_chapter_scope']})


def test_compile_preserves_formula_numeric_conditions_and_all_units():
    p,f,b,v=sample();approve_plan(p,approval(p,f,b),f,b,['主题'])
    draft,units=compile_report(p,f,b,v,['主题'])
    assert len(units)==10 and len(draft.chapters)==5
    assert r'L=\sum_i e_i^2' in units['s2']
    assert '1000 / joint' in units['s4'] and '50000 / energy' in units['s4']
    assert '0.08 kcal/mol' in units['s4'] and '0.07 kcal/mol' in units['s4']


@pytest.mark.parametrize('change',['plan','facts','source','reviewer','coverage'])
def test_stale_or_incomplete_approval_rejected(change):
    p,f,b,v=sample();a=approval(p,f,b)
    if change=='plan':p.results[0].train_n='2000'
    if change=='facts':f['f0']['condition']='changed'
    if change=='source':b['p1b1']['text']='changed'
    if change=='reviewer':a['reviewer_kind']='deepseek'
    if change=='coverage':a['required_unit_ids'].pop()
    with pytest.raises(ValueError):approve_plan(p,a,f,b,['主题'])


@pytest.mark.parametrize('change',['missing_chapter','orphan_formula','duplicate_result','unknown_fact','unknown_source'])
def test_invalid_plan_ownership(change):
    p,f,b,v=sample()
    if change=='missing_chapter':p.units=[u for u in p.units if u.chapter!=4]
    if change=='orphan_formula':p.units[2].formula_ids=[]
    if change=='duplicate_result':p.units[5].result_ids=['r1']
    if change=='unknown_fact':p.units[0].fact_ids=['f99']
    if change=='unknown_source':p.formulas[0].evidence_ids=['p99b1']
    with pytest.raises(ValueError):check_plan(p,f,b,['主题'])


def test_conditional_comparison_requires_explicit_axes():
    p,*_=sample()
    with pytest.raises(ValueError,match='train_n'):compare_results(p,'r1','r2','difference')
    assert compare_results(p,'r1','r2','difference',['train_n','supervision'])=='-0.01'
    p.results[1].split='different'
    with pytest.raises(ValueError,match='split'):compare_results(p,'r1','r2','difference',['train_n','supervision'])


@pytest.mark.parametrize('value',['NaN','Infinity','-Infinity','abc','1e9999999'])
def test_nonfinite_value_rejected(value):
    p,*_=sample();data=p.results[0].model_dump();data['value']=value
    with pytest.raises(ValueError):Result(**data)


def test_missing_unknown_zero_not_fabricated():
    p,f,b,v=sample();p.results[0].value=None
    with pytest.raises(ValueError):check_plan(p,f,b,['主题'])
    p.results[0].unavailable_reason='not reported';check_plan(p,f,b,['主题'])
    with pytest.raises(ValueError):compare_results(p,'r1','r2','difference',['train_n','supervision'])
    p.results[0].value='0';p.results[0].unavailable_reason='';p.results[1].train_n=p.results[0].train_n;p.results[1].supervision=p.results[0].supervision
    with pytest.raises(ValueError,match='Zero'):compare_results(p,'r1','r2','relative_percent')
    p.results[1].protocol='未知'
    with pytest.raises(ValueError,match='Unknown'):compare_results(p,'r1','r2','difference')


@pytest.mark.parametrize('suffix',[' 0.08',' １２','$x$','| table |'])
def test_free_prose_cannot_rewrite_numeric_or_formula(suffix):
    p,f,b,v=sample();v.units[0].text+=suffix
    with pytest.raises(ValueError):check_explanations(v,[u.id for u in p.units])


def test_missing_or_duplicate_explanation_rejected():
    p,f,b,v=sample();v.units[-1]=v.units[0]
    with pytest.raises(ValueError):check_explanations(v,[u.id for u in p.units])


def test_repair_only_target_changes_and_source_units_preserved(tmp_path):
    p,f,b,v=sample()
    class Fake:
        config={'model':'test'}
        def json_mode(self,*args):pass
        def generate(self,prompt):return {'units':[{'unit_id':'s0','text':v.units[0].text+'修订解释仅缩小原文结论的适用范围。'}]}
    packet={'round':1,'previous_sha256':digest(v.model_dump()),'plan_sha256':digest(p.model_dump()),'issues':[{'unit_id':'s0','defect_id':'scope','finding':'Narrow scope'}]}
    fixed=explain(Fake(),p,f,tmp_path/'r1',repair=packet,previous=v)
    assert fixed.units[1:]==v.units[1:]
    _,old=compile_report(p,f,b,v,['主题']);_,new=compile_report(p,f,b,fixed,['主题'])
    assert all(old[k]==new[k] for k in old if k!='s0')
    packet['round']=3
    with pytest.raises(ValueError):explain(Fake(),p,f,tmp_path/'r3',repair=packet,previous=v)


def test_unchanged_repair_rejected(tmp_path):
    p,f,b,v=sample()
    class Fake:
        config={'model':'test'}
        def json_mode(self,*args):pass
        def generate(self,prompt):return {'units':[v.units[0].model_dump()]}
    packet={'round':1,'previous_sha256':digest(v.model_dump()),'plan_sha256':digest(p.model_dump()),'issues':[{'unit_id':'s0','defect_id':'scope','finding':'Narrow scope'}]}
    with pytest.raises(ValueError):explain(Fake(),p,f,tmp_path,repair=packet,previous=v)


def test_plan_patch_preserves_unrequested_fields():
    from backend.study_compiler import repair_plan
    p,f,b,v=sample();packet={'round':1,'previous_sha256':digest(p.model_dump()),'fields':['summary'],'findings':['Narrow summary scope']}
    class Fake:
        config={'model':'test'}
        def json_mode(self,*args):pass
        def generate(self,prompt):return {'replacements':{'summary':p.summary+'此结论不能推广到未测试的任务或数据集。'}}
    fixed=repair_plan(Fake(),p,packet,f,b,['主题'])
    assert fixed.units==p.units and fixed.results==p.results and fixed.formulas==p.formulas
    packet['previous_sha256']='stale'
    with pytest.raises(ValueError):repair_plan(Fake(),p,packet,f,b,['主题'])

import copy,hashlib
import pytest
from backend.llm_runtime import packed
from backend.study_review import reviewed_context,numeric_comparison,FACETS


def fixture():
    fact=dict(kind='method',statement='Actual method description',evidence_ids=['p1b1'],condition='Named model and task',needs_visual_review=False)
    inventory={'units':[{'facts':[fact]}]}
    blocks={'p1b1':dict(page=1,text='Actual source'), 'p2b1':dict(page=2,text='Continued paragraph')}
    h=lambda x:hashlib.sha256(packed(x).encode()).hexdigest()
    review=dict(inventory_sha256=h(inventory),source_blocks_sha256=h(blocks),reviewer_kind='codex',reviewer='editor',status='approved',blocking_issues=[],facts=[dict(id='u0:f0',fact_sha256=h(fact),decision='approved',rationale='Checked original mechanism')],facets={k:dict(status='covered',rationale='Source inspected',evidence_ids=['p1b1']) for k in FACETS})
    return inventory,blocks,review


def test_review_binds_actual_source_and_retains_continuation():
    inv,blocks,review=fixture()
    facts,context=reviewed_context(inv,blocks,review)
    assert len(facts)==1 and 'p2b1' in context
    blocks['p1b1']['text']='Changed source'
    with pytest.raises(ValueError,match='source snapshot'):reviewed_context(inv,blocks,review)


def test_model_approval_or_unresolved_coverage_cannot_enter_report():
    inv,blocks,review=fixture()
    review['reviewer_kind']='deepseek'
    with pytest.raises(ValueError,match='Independent'):reviewed_context(inv,blocks,review)
    review['reviewer_kind']='codex';review['facets'].pop('mechanism')
    with pytest.raises(ValueError,match='core review facets'):reviewed_context(inv,blocks,review)


def test_numeric_scope_and_percentage_are_not_interchangeable():
    base=dict(status='approved',source='page 9, Table 3',task='AlpacaEval',metric='LC win rate',unit='percent',protocol='Table 3')
    left=dict(base,value='87.6');right=dict(base,value='62.1')
    assert numeric_comparison(left,right,'difference')=='25.5'
    assert numeric_comparison(left,right,'relative_percent').startswith('41.06')
    right['metric']='accuracy'
    with pytest.raises(ValueError,match='metric'):numeric_comparison(left,right,'difference')

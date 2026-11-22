import pytest
from decimal import Decimal
from backend.evidence_ledger import ResultCell,VerifiedCell,fingerprint,compare


def cell(value,**changes):
    data=dict(id='f1',source_hash='source',page=7,table='1',row='model',column='runtime',metric='time_to_target',
              value=value,unit='minutes',model='baseline',dataset='Wikipedia',split='MLPerf validation',
              protocol='72% MLM; 10 runs',hardware='8 A100 80GB')
    data.update(changes);v=ResultCell(**data)
    return VerifiedCell(cell=v,reviewed_cell_hash=fingerprint(v))


def test_flash_runtime_speedup_is_not_percent_time_reduction():
    a,b=cell('20'),cell('17.4',model='FlashAttention')
    assert compare(a,b,'speedup')==Decimal('20')/Decimal('17.4')
    assert compare(a,b,'relative_change')==Decimal('-.13')


def test_wrong_units_and_changed_context_cannot_be_combined():
    a=cell('2347',unit='seconds',metric='registration_runtime')
    b=cell('41251',unit='voxels',metric='nonpositive_jacobian')
    with pytest.raises(ValueError,match='metric'):compare(a,b,'speedup')
    with pytest.raises(ValueError,match='protocol'):compare(cell(20),cell(17,protocol='different target'),'speedup')


def test_edited_fact_requires_review_and_auc_has_no_weighted_average_shortcut():
    a=cell(20);a.cell.value=Decimal(21)
    with pytest.raises(ValueError,match='changed'):compare(a,cell(17),'speedup')
    with pytest.raises(ValueError,match='Unsupported'):compare(cell(20),cell(17),'weighted_auc')

"""Deterministic result comparison over verified, source-bound experiment cells.

The ledger deliberately does not infer column ownership from flat PDF text.
Only a separately reviewed table/caption mapping can set the verified marker.
"""
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field


class ResultCell(BaseModel):
    id: str
    source_hash: str
    page: int = Field(ge=1)
    table: str
    row: str
    column: str
    metric: str
    value: Decimal
    unit: str
    model: str
    dataset: str
    split: str
    protocol: str
    hardware: str | None = None


class VerifiedCell(BaseModel):
    cell: ResultCell
    reviewed_cell_hash: str


def fingerprint(cell):
    import hashlib
    return hashlib.sha256(cell.model_dump_json().encode()).hexdigest()


def compare(left: VerifiedCell, right: VerifiedCell,
            operation: Literal['difference','percentage_points','speedup','relative_change']):
    """Comparisons require aligned experimental conditions, not just two numbers."""
    for record in (left,right):
        if fingerprint(record.cell)!=record.reviewed_cell_hash:
            raise ValueError('Cell changed after source review')
    a,b=left.cell,right.cell
    for field in ('source_hash','metric','unit','dataset','split','protocol','hardware'):
        if getattr(a,field)!=getattr(b,field):
            raise ValueError('Incompatible experiment '+field)
    if not all((a.metric,a.unit,a.dataset,a.split,a.protocol,b.model,a.model)):
        raise ValueError('Experiment context is incomplete')
    if operation=='percentage_points':
        if a.unit!='percent':raise ValueError('Percentage-point difference requires percent values')
        return b.value-a.value
    if operation=='difference':return b.value-a.value
    if operation=='relative_change':
        if not a.value:raise ValueError('Zero reference value')
        return (b.value-a.value)/a.value
    if operation=='speedup':
        if a.unit not in {'seconds','milliseconds','minutes','hours','days'}:
            raise ValueError('Speedup requires runtime measurements')
        if a.value<=0 or b.value<=0:raise ValueError('Runtime must be positive')
        return a.value/b.value
    raise ValueError('Unsupported operation')

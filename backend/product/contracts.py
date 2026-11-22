"""Bounded product inputs; callers never supply original evidence text."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CandidateCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid', strict=True)
    paper_id: str = Field(min_length=1, max_length=200)
    reason: str = Field(default='', max_length=5000)


class CandidateEdit(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid', strict=True)
    revision: int = Field(ge=1)
    status: Literal['pending', 'kept', 'excluded']
    reason: str = Field(max_length=5000)

    @model_validator(mode='after')
    def substantive_reason(self):
        if self.status != 'pending' and len(self.reason) < 4:
            raise ValueError('保留或排除候选需至少4字的实质理由')
        return self


class TrendLeadCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid', strict=True)
    series_id: str = Field(min_length=1, max_length=200)
    start: str = Field(min_length=4, max_length=7)
    end: str = Field(min_length=4, max_length=7)
    interval: Literal['year', 'month']
    period: str | None = Field(default=None, max_length=7)
    focus_paper_id: str | None = Field(default=None, min_length=1, max_length=200)
    source_key: str = Field(pattern=r'^[a-f0-9]{64}$')
    reason: str = Field(min_length=4, max_length=5000)
    paper_ids: list[str] = Field(default_factory=list, max_length=24)

    @field_validator('paper_ids')
    @classmethod
    def bounded_paper_ids(cls, values):
        if any(not value.strip() or len(value) > 200 for value in values):
            raise ValueError('论文ID需为1至200字符')
        return list(dict.fromkeys(value.strip() for value in values))


class TrendLeadEdit(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid', strict=True)
    revision: int = Field(ge=1)
    status: Literal['pending', 'kept', 'excluded']
    reason: str = Field(min_length=4, max_length=5000)


class PaperIntakeCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid', strict=True)
    revision: int = Field(ge=1)
    paper_id: str = Field(min_length=1, max_length=200)
    domain_id: str = Field(min_length=1, max_length=200)
    analyze: bool = False


class PaperIntakeAction(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    revision: int = Field(ge=1)


class Criterion(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,60}$')
    label: str = Field(min_length=2, max_length=120)


class ProjectCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=2, max_length=160)
    scenario: Literal['route_review', 'material_substitution', 'change_review']
    owner: str = Field(default='', max_length=100)
    question: str = Field(min_length=10, max_length=5000)
    constraints: str = Field(default='', max_length=5000)
    criteria: list[Criterion] = Field(min_length=1, max_length=8)

    @field_validator('criteria')
    @classmethod
    def unique_criteria(cls, value):
        if len({x.id for x in value}) != len(value):
            raise ValueError('评价标准ID不能重复')
        return value


class ProjectEdit(ProjectCreate):
    # Scenario is fixed after creation; it is not part of edit requests.
    scenario: Literal['route_review', 'material_substitution', 'change_review'] | None = None
    revision: int = Field(ge=1)
    recommendation: str = Field(default='', max_length=15000)
    open_questions: str = Field(default='', max_length=10000)


class EvidenceInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    revision: int = Field(ge=1)
    analysis_id: int = Field(gt=0)
    claim_index: int = Field(ge=0)
    criterion_id: str = Field(min_length=1, max_length=60)
    stance: Literal['supports', 'contradicts', 'uncertain']
    context: str = Field(min_length=4, max_length=3000)


class ReviewInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    revision: int = Field(ge=1)
    reviewer: str = Field(min_length=2, max_length=100)
    note: str = Field(min_length=8, max_length=5000)


class DeliveryInput(BaseModel):
    revision: int = Field(ge=1)


class ValidationCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    revision: int = Field(ge=1)
    criterion_id: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=4, max_length=180)
    success_criteria: str = Field(min_length=8, max_length=3000)
    owner: str = Field(min_length=2, max_length=100)


class ValidationEdit(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    revision: int = Field(ge=1)
    status: Literal['planned', 'completed']
    outcome: Literal['pending', 'supports', 'contradicts', 'inconclusive']
    observation: str = Field(default='', max_length=10000)


SCENARIOS = [
    dict(id='route_review', title='技术路线立项评审',
         description='比较候选路线的性能、工况与验证成本，保留选取和放弃的依据。',
         question='在目标工况和现有研发能力下，哪条技术路线值得进入下一轮验证？',
         constraints='填写目标性能、适用环境、预算和验证周期；区别论文条件与真实工况。',
         criteria=[dict(id='performance', label='目标性能与适用工况'), dict(id='feasibility', label='实现与验证可行性'), dict(id='risk', label='失败风险与证据缺口')],
         deliverable='候选路线决策包与下一轮验证问题'),
    dict(id='material_substitution', title='材料替代与降本验证',
         description='从目标性能和工艺约束出发，组织替代材料的支持证据与反例。',
         question='在性能和工艺边界不变的条件下，哪种材料替代方案值得试验？',
         constraints='填写温度、环境、工艺兼容性、成本口径及不可降低的性能指标。',
         criteria=[dict(id='performance', label='性能保持与工况差异'), dict(id='process', label='工艺兼容与验证成本'), dict(id='risk', label='反例与未验证条件')],
         deliverable='替代假设、证据差异与实验验证清单'),
    dict(id='change_review', title='技术变化触发项目复审',
         description='把新证据关联到既有项目判断，识别哪些结论需要重新验证。',
         question='新出现的技术证据是否改变现有路线选择，哪些判断需要复审？',
         constraints='填写既有决策、触发变化、客户工况及下一次评审节点。',
         criteria=[dict(id='impact', label='对既有判断的影响'), dict(id='transfer', label='新结果的条件可迁移性'), dict(id='action', label='后续验证与行动条件')],
         deliverable='变更前后依据、影响范围与复审决策'),
]

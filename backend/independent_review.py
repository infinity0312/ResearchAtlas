"""Source-bound independent review receipts for collaboration publications.

Receipts annotate immutable analyses. Model labels and generic quality flags are
never review evidence; exact reviewed report/extraction hashes are required.
"""
import copy
import hashlib
import json

from pydantic import BaseModel, Field

from .contracts import Extraction
from .analysis_pipeline import claim_id, verified_claims
from .evidence_contracts import PIPELINE_VERSION, valid_grounding

FACETS = {'identity', 'coverage', 'claims', 'mathematics', 'numbers',
          'experiments', 'limitations', 'classification', 'prose'}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf8')).hexdigest()


def text_hash(value):
    return hashlib.sha256(value.encode('utf8')).hexdigest()


class ReviewReceipt(BaseModel):
    model_config = {'extra': 'allow'}
    decision: str
    blocking_issues: list = Field(default_factory=list)
    reviewer_model: str = Field(min_length=1, max_length=100)
    reviewer_agent: str = Field(min_length=1, max_length=200)
    report_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    result_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    content_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    reviewed_pages: list[int] = Field(min_length=1, max_length=3000)
    checks: dict


def check_receipt(receipt, report_hash, raw_hash, content_hash, pages, claim_pages):
    if receipt.decision != 'approved' or receipt.blocking_issues:
        raise ValueError('复核记录未批准或仍有阻塞问题')
    if (receipt.report_sha256, receipt.result_sha256, receipt.content_hash) != (
            report_hash, raw_hash, content_hash):
        raise ValueError('复核记录与全文报告、结构结果或原文版本不匹配')
    checked = set(receipt.reviewed_pages)
    if not claim_pages <= checked or not checked <= pages:
        raise ValueError('复核页码缺少引用上下文或包含不存在的页码')
    if not FACETS <= receipt.checks.keys():
        raise ValueError('缺少独立科学复核维度')
    for name in FACETS:
        check = receipt.checks[name]
        if not isinstance(check, dict) or check.get('status') not in ('passed', 'not_applicable') \
                or not isinstance(check.get('note'), str) or not check['note'].strip():
            raise ValueError('科学复核维度未通过：' + name)


def bind_fields(result, additions):
    """Add traceability without changing scientific wording or old snapshots."""
    result = copy.deepcopy(result)
    claims = result['claims']
    if len({claim_id(c) for c in claims}) != len(claims):
        raise ValueError('重复结论不能形成唯一证据绑定')
    refs = dict(result.get('field_evidence', {}))
    for key, value in additions.items():
        refs[key] = list(dict.fromkeys([*refs.get(key, []), *value]))
    used = set()
    grounding = {}
    for field in ('summary', 'topics', 'methods', 'problems'):
        values = [result[field]] if field == 'summary' else result[field]
        grounding[field] = []
        for i, value in enumerate(values):
            key = field if field == 'summary' else f'{field}.{i}'
            indices = refs.get(key, [])
            if not indices or any(type(j) is not int or j < 0 or j >= len(claims) for j in indices) \
                    or len(indices) != len(set(indices)):
                raise ValueError('结论字段缺少有效依据绑定：' + key)
            # A reviewed experiment/protocol claim may be classified as a
            # contribution while supporting an evaluation-method label. The
            # explicit scientific reviews adjudicate semantics; IDs establish
            # traceability and never imply entailment on their own.
            grounding[field].append({'text': value, 'claim_ids': [claim_id(claims[j]) for j in indices]})
            used.add(key)
    if set(additions) - used:
        raise ValueError('追加绑定字段不存在')
    result['claims'] = [{**c, 'id': claim_id(c)} for c in claims]
    result.update(field_evidence=refs, grounding=grounding, prompt_version=PIPELINE_VERSION)
    if not valid_grounding(result):
        raise ValueError('复核结果未通过结论绑定校验')
    return result


def make_certificate(analysis, pages, raw_result, generation_agent, independent, coordinator,
                     binding_additions=None, binding_note='', raw_report=None):
    raw = json.loads(raw_result)
    extraction = Extraction.model_validate(raw.get('result', raw)).model_dump()
    current = Extraction.model_validate(analysis.result).model_dump()
    if extraction != current:
        raise ValueError('复核结构结果不是该分析的原始结果')
    if generation_agent in (independent.reviewer_agent, coordinator.reviewer_agent) \
            or independent.reviewer_agent == coordinator.reviewer_agent:
        raise ValueError('生成者、独立复核者和协调复核者必须分开')
    if independent.reviewer_model != 'gpt-6.1-sol':
        raise ValueError('此全文批次需要6.1sol独立复核记录')
    report = analysis.result.get('fulltext_markdown', '')
    if not report:
        raise ValueError('该分析没有全文研读报告')
    reviewed_report = report if raw_report is None else raw_report
    if reviewed_report.replace('\r\n', '\n').strip() != report.replace('\r\n', '\n').strip():
        raise ValueError('复核报告正文与已发布分析不同')
    claims = extraction['claims']
    if not claims or len(verified_claims(claims, pages)) != len(claims):
        raise ValueError('原文引文未全部通过校验')
    numbers = {p['page'] for p in pages}
    claim_pages = {part['page'] for c in claims for part in [c, *c['supporting_evidence']]}
    for receipt in (independent, coordinator):
        check_receipt(receipt, text_hash(reviewed_report), text_hash(raw_result), analysis.content_hash,
                      numbers, claim_pages)
    additions = binding_additions or {}
    if additions and len(binding_note.strip()) < 10:
        raise ValueError('追加字段绑定必须记录人工核查依据')
    bound = bind_fields(extraction, additions)
    view = {**copy.deepcopy(analysis.result), **bound}
    return {'contract_version': 1, 'analysis_id': analysis.id,
            'analysis_payload_sha256': fingerprint(analysis.result),
            'content_hash': analysis.content_hash, 'report_sha256': text_hash(reviewed_report),
            'stored_report_sha256': text_hash(report),
            'extraction_sha256': fingerprint(extraction), 'generation_agent': generation_agent,
            'independent': independent.model_dump(), 'coordinator': coordinator.model_dump(),
            'binding_additions': additions, 'binding_note': binding_note,
            'grounded_result': view, 'grounded_result_sha256': fingerprint(view)}


def certificate_result(analysis, certificate):
    """Revalidate stored annotation on every read; a changed analysis loses it."""
    if not isinstance(certificate, dict) or certificate.get('contract_version') != 1:
        return None
    if certificate.get('analysis_id') != analysis.id \
            or certificate.get('analysis_payload_sha256') != fingerprint(analysis.result) \
            or certificate.get('content_hash') != analysis.content_hash:
        return None
    view = certificate.get('grounded_result')
    if not isinstance(view, dict) or certificate.get('grounded_result_sha256') != fingerprint(view) \
            or view.get('fulltext_markdown') != analysis.result.get('fulltext_markdown') \
            or view.get('prompt_version') != PIPELINE_VERSION or not valid_grounding(view):
        return None
    return view

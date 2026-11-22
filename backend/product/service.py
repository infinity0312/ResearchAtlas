"""Transactional project lifecycle and evidence-aware delivery gates.

No model calls and no independent quality inference. The literature domain is
read through its existing review contract; product decisions remain explicit.
"""
import hashlib
import json
from urllib.parse import quote
from sqlalchemy import select
from fastapi import HTTPException
from ..db import Analysis, Domain, Paper, now, serialize
from ..analysis_repository import current_query, read_analysis, review_certificates, source_updates
from .models import ResearchProject, ProjectEvidence, ProjectReview, ProjectDelivery, ProductEvent, ProjectValidation


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf8')).hexdigest()


def project(s, pid, revision=None):
    p = s.get(ResearchProject, pid)
    if p is None:
        raise HTTPException(404, '研发项目不存在')
    if revision is not None and p.revision != revision:
        raise HTTPException(409, '项目已被修改，请保留输入并重新载入最新版本')
    return p


def event(s, p, action, detail=None, actor=None):
    s.add(ProductEvent(project_id=p.id, action=action, revision=p.revision,
                       actor=(actor or p.owner or '本机操作者'), detail=detail or {}))


def changed(s, p, action, detail=None):
    p.revision += 1
    p.updated = now()
    p.status = 'draft'
    event(s, p, action, detail)


def analysis_view(s, a):
    paper, domain = s.get(Paper, a.paper_id), s.get(Domain, a.domain_id)
    if paper is None or domain is None:
        return None
    return read_analysis(a, paper, domain, source_updates(s, [paper.id]), full=True,
                         independent_review=review_certificates(s, [a.id]).get(a.id))


def evidence_health(s, e):
    a = s.get(Analysis, e.analysis_id)
    issues = []
    if a is None:
        return dict(eligible=False, issues=['原分析已不存在'], quality=None, latest_analysis_id=None)
    latest = s.scalars(current_query([e.paper_id], a.domain_id)).first()
    latest_id = latest.id if latest else None
    snapshot = e.snapshot if isinstance(e.snapshot, dict) else {}
    required = ('content_hash', 'claim_digest', 'paper_version', 'paper_title',
                'domain_id', 'taxonomy_version', 'claim_index', 'claim_text',
                'claim_kind', 'page', 'quote')
    if any(key not in snapshot for key in required):
        return dict(eligible=False, issues=['绑定来源快照不完整，需重新核对并绑定'],
                    quality=None, latest_analysis_id=latest_id)
    if not isinstance(a.result, dict) or not isinstance(a.result.get('claims'), list):
        return dict(eligible=False, issues=['原分析缺少有效主张结构，需重新核对'],
                    quality=None, latest_analysis_id=latest_id)
    claims = a.result['claims']
    if (type(e.claim_index) is not int or e.claim_index < 0 or e.claim_index >= len(claims)
            or not isinstance(claims[e.claim_index], dict)):
        return dict(eligible=False, issues=['绑定主张已不存在或结构无效，需重新核对'],
                    quality=None, latest_analysis_id=latest_id)
    claim = claims[e.claim_index]
    if (a.paper_id != e.paper_id or a.domain_id != snapshot['domain_id']
            or a.version != snapshot['paper_version']
            or a.taxonomy_version != snapshot['taxonomy_version']
            or e.claim_index != snapshot['claim_index']
            or any(claim.get(field) != snapshot[snap] for field, snap in
                   [('text', 'claim_text'), ('kind', 'claim_kind'), ('page', 'page'), ('quote', 'quote')])):
        return dict(eligible=False, issues=['来源身份或引文与绑定快照不一致，需重新核对'],
                    quality=None, latest_analysis_id=latest_id)
    view = analysis_view(s, a)
    if view is None:
        return dict(eligible=False, issues=['文献或领域已不存在'], quality=None, latest_analysis_id=None)
    q = view['quality']
    claims = (a.result or {}).get('claims', [])
    if a.content_hash != e.snapshot['content_hash'] or e.claim_index >= len(claims) or digest(claims[e.claim_index]) != e.snapshot['claim_digest']:
        issues.append('原始分析内容与绑定快照不一致')
    if latest is None or latest.id != e.analysis_id:
        issues.append('文献已有新分析，请重新选择证据')
    if q['freshness'] != 'current':
        issues.append('来源、论文或分类版本已变化')
    if q['evidence'] != 'verified' or q['grounding'] != 'bound':
        issues.append('原文引文或结论绑定尚未核验')
    if q['semantic'] not in ('model_reviewed', 'human_reviewed'):
        issues.append('分析尚未完成独立语义复核')
    if e.stance == 'uncertain':
        issues.append('待核证据需明确立场后重新录入')
    return dict(eligible=not issues, issues=issues, quality=q,
                latest_analysis_id=latest.id if latest else None)


def evidence_rows(s, pid):
    return list(s.scalars(select(ProjectEvidence).where(ProjectEvidence.project_id == pid)
                          .order_by(ProjectEvidence.created, ProjectEvidence.id)))


def fingerprint(p, evidence, validations):
    # Actual live quality is included: review revocation/source change cannot be
    # hidden behind an unchanged product revision.
    return digest(dict(project={k:v for k,v in serialize(p).items() if k not in ('status','revision','updated')},
                       evidence=[dict(id=e['id'], criterion_id=e['criterion_id'], stance=e['stance'],
                                      context=e['context'], snapshot=e['snapshot'], health=e['health']) for e in evidence],
                       validations=validations))


def detail(s, p):
    evidence = [{**serialize(e), 'health': evidence_health(s, e)} for e in evidence_rows(s, p.id)]
    reviews = list(s.scalars(select(ProjectReview).where(ProjectReview.project_id == p.id)
                            .order_by(ProjectReview.created.desc(), ProjectReview.id.desc())))
    deliveries = list(s.scalars(select(ProjectDelivery).where(ProjectDelivery.project_id == p.id)
                               .order_by(ProjectDelivery.sequence.desc())))
    blockers = []
    if not p.owner.strip(): blockers.append('填写项目负责人')
    if len(p.question.strip()) < 10: blockers.append('补充明确的决策问题')
    if len(p.recommendation.strip()) < 10: blockers.append('填写决策建议及适用条件（至少10字）')
    covered = {e['criterion_id'] for e in evidence if e['health']['eligible']}
    for c in p.criteria:
        if c['id'] not in covered: blockers.append('评价标准缺少有效证据：' + c['label'])
    for e in evidence:
        if not e['health']['eligible']:
            blockers.append(e['snapshot']['paper_title'] + '：' + '；'.join(e['health']['issues']))
    validations=[serialize(v) for v in s.scalars(select(ProjectValidation).where(ProjectValidation.project_id==p.id)
                  .order_by(ProjectValidation.created,ProjectValidation.id))]
    fp = fingerprint(p, evidence, validations)
    # A delivered revision may be exported again without minting a second copy.
    reviewed = bool(reviews and reviews[0].evidence_fingerprint == fp and
                    p.status in ('reviewed', 'delivered'))
    pending_validations = sum(v['status'] == 'planned' for v in validations)
    if any(not e['health']['eligible'] for e in evidence):
        action, label = 'repair_evidence', '核对并修订待处理证据'
    elif not p.owner.strip() or len(p.question.strip()) < 10 or len(p.recommendation.strip()) < 10:
        action, label = 'complete_decision', '补齐负责人和决策建议'
    elif any(c['id'] not in covered for c in p.criteria):
        action, label = 'collect_evidence', '为未覆盖的标准补充证据'
    elif not reviewed:
        action, label = 'review_decision', '核对当前依据并记录评审'
    elif p.status != 'delivered':
        action, label = 'freeze_delivery', '生成当前版本交付'
    elif pending_validations:
        action, label = 'run_validation', '执行验证并回写实际结果'
    else:
        action, label = 'monitor_sources', '交付已归档，关注后续证据变化'
    ready = dict(can_review=not blockers, can_deliver=not blockers and reviewed,
                 blockers=blockers, evidence_count=len(evidence),
                 contradiction_count=sum(e['stance']=='contradicts' for e in evidence),
                 stale_count=sum(not e['health']['eligible'] for e in evidence),
                 covered_criteria=len(covered), total_criteria=len(p.criteria),
                 review_valid=reviewed, review_outdated=bool(reviews and not reviewed),
                 pending_validations=pending_validations, next_action=action, next_action_label=label)
    return dict(project=serialize(p), evidence=evidence, validations=validations, reviews=[serialize(r) for r in reviews],
                deliveries=[{k:v for k,v in serialize(r).items() if k not in ('manifest','markdown')} for r in deliveries],
                events=[serialize(e) for e in s.scalars(select(ProductEvent).where(ProductEvent.project_id==p.id)
                        .order_by(ProductEvent.created.desc(), ProductEvent.id.desc()).limit(100))],
                readiness=ready)


def make_evidence(s, p, data, excluding_id=None):
    """Validate before retiring a binding; source snapshots are server selected."""
    if data.criterion_id not in {c['id'] for c in p.criteria}:
        raise HTTPException(422, '评价标准不属于当前项目')
    a = s.get(Analysis, data.analysis_id)
    if a is None: raise HTTPException(404, '分析不存在')
    claims = (a.result or {}).get('claims', [])
    if data.claim_index >= len(claims): raise HTTPException(422, '原始主张不存在')
    c = claims[data.claim_index]
    if not isinstance(c,dict) or not c.get('text') or not c.get('quote') or not c.get('page'):
        raise HTTPException(422, '原始主张缺少文本、页码或引文')
    duplicate = select(ProjectEvidence.id).where(ProjectEvidence.project_id==p.id,
            ProjectEvidence.analysis_id==a.id,ProjectEvidence.claim_index==data.claim_index,
            ProjectEvidence.criterion_id==data.criterion_id)
    if excluding_id is not None:
        duplicate = duplicate.where(ProjectEvidence.id != excluding_id)
    if s.scalar(duplicate):
        raise HTTPException(409, '该主张已绑定此评价标准，请先检查已有证据')
    view = analysis_view(s, a)
    if view is None: raise HTTPException(422, '分析的文献或领域已不存在')
    paper = s.get(Paper, a.paper_id)
    return ProjectEvidence(project_id=p.id,analysis_id=a.id,paper_id=a.paper_id,
        claim_index=data.claim_index,criterion_id=data.criterion_id,stance=data.stance,
        context=data.context.strip(),snapshot=dict(paper_title=paper.title,domain_id=a.domain_id,
        paper_version=a.version,taxonomy_version=a.taxonomy_version,content_hash=a.content_hash,
        claim_index=data.claim_index,claim_text=c['text'],claim_kind=c.get('kind',''),
        page=c['page'],quote=c['quote'],claim_digest=digest(c),quality=view['quality']))


def attach(s, p, data):
    e = make_evidence(s, p, data)
    s.add(e);s.flush();changed(s,p,'evidence_attached',dict(evidence_id=e.id,analysis_id=e.analysis_id))
    return {**serialize(e),'health':evidence_health(s,e)}


def replace_evidence(s, p, old, data):
    fields = ('analysis_id', 'claim_index', 'criterion_id', 'stance', 'context')
    if all(getattr(old, k) == getattr(data, k) for k in fields):
        return {**serialize(old), 'health': evidence_health(s, old)}
    replacement = make_evidence(s, p, data, excluding_id=old.id)
    before = serialize(old)
    # One transaction: failed validation/insert never leaves a missing binding.
    # Old snapshots remain in the append-only event and any frozen deliveries.
    s.delete(old);s.flush()
    s.add(replacement);s.flush()
    changed(s, p, 'evidence_replaced', dict(before=before, after=serialize(replacement)))
    return {**serialize(replacement), 'health': evidence_health(s, replacement)}


def review(s, p, data):
    d = detail(s,p)
    if not d['readiness']['can_review']:
        raise HTTPException(422, '暂不能评审：' + '；'.join(d['readiness']['blockers']))
    if not data.reviewer.strip() or not data.note.strip():
        raise HTTPException(422, '填写评审署名与实质评审意见')
    p.revision += 1;p.updated=now();p.status='reviewed'
    r=ProjectReview(project_id=p.id,project_revision=p.revision,
        evidence_fingerprint=fingerprint(p,d['evidence'],d['validations']),reviewer=data.reviewer.strip(),note=data.note.strip())
    s.add(r);s.flush();event(s,p,'review_recorded',dict(review_id=r.id),data.reviewer.strip())
    return serialize(r)


def markdown(manifest):
    p=manifest['project'];lines=['# '+p['title'],'', '## 决策问题','',p['question'],'',
        '## 工况与约束','',p['constraints'] or '未填写','', '## 决策建议','',p['recommendation'],'',
        '## 未解问题与验证条件','',p['open_questions'] or '未记录；不代表没有不确定性。','',
        '## 证据与反例','']
    labels={c['id']:c['label'] for c in p['criteria']}
    for e in manifest['evidence']:
        x=e['snapshot'];stance={'supports':'支持','contradicts':'反对','uncertain':'待核'}[e['stance']]
        lines += [f"### {labels[e['criterion_id']]} · {stance}",'',x['claim_text'],'',
            '适用性说明：'+e['context'],'',f"来源：{x['paper_title']}，第{x['page']}页；分析 #{e['analysis_id']}，论文版本{x['paper_version']}。",'',
            '> '+x['quote'].replace('\n','\n> '),'',f"[核对原文PDF版本与页码](http://127.0.0.1:8765/api/paper/pdf?id={quote(e['paper_id'],safe='')}&version={x['paper_version']}#page={x['page']})",'']
    lines += ['## 验证计划与内部结果','', '以下为团队手工记录，未独立核验，不替代论文证据。','']
    for v in manifest['validations']:
        lines += ['### '+v['title'],'', '验收标准：'+v['success_criteria'],'',
                  '负责人：'+v['owner']+'；状态：'+('已记录结果' if v['status']=='completed' else '待验证')+'；结果：'+v['outcome'],'',
                  '观察：'+(v['observation'] or '尚无实际观察。'),'']
    r=manifest['review'];lines += ['## 评审与版本','',f"项目负责人：{p['owner']}；评审署名：{r['reviewer']}；评审时间：{r['created']}。",'',r['note'],'',
        '署名是本机手工记录，未经组织身份认证。该交付冻结上述版本与短引文，不包含论文PDF或未经核查的外部附件。']
    return '\n'.join(lines)+'\n'


def deliver(s,p):
    d=detail(s,p)
    if not d['readiness']['can_deliver']:
        raise HTTPException(422, '交付需要当前有效评审及全部有效证据；'+ '；'.join(d['readiness']['blockers']))
    r=d['reviews'][0]
    existing=s.scalar(select(ProjectDelivery).where(ProjectDelivery.project_id==p.id)
        .order_by(ProjectDelivery.sequence.desc()))
    if existing and existing.manifest['review']['id']==r['id']:
        return serialize(existing)
    seq=(existing.sequence if existing else 0)+1
    evidence=[]
    for e in d['evidence']:
        x=json.loads(canonical(e));text=x['snapshot']['quote']
        if len(text)>600:x['snapshot']['quote']=text[:600]+'… [节选]'
        evidence.append(x)
    manifest=dict(schema_version=1,project=d['project'],review=r,evidence=evidence,validations=d['validations'],
                  scope='local-single-organization-pilot',attachments_included=False,
                  evidence_policy='quoted-analysis-snapshots; no PDF redistribution',created=now())
    body=markdown(manifest)
    delivery=ProjectDelivery(project_id=p.id,sequence=seq,source_revision=p.revision,
        title=p.title+f' · 交付{seq}',manifest=manifest,markdown=body,
        digest=digest(dict(manifest=manifest,markdown=body)))
    s.add(delivery);s.flush();p.revision+=1;p.updated=now();p.status='delivered'
    event(s,p,'delivery_frozen',dict(delivery_id=delivery.id,sequence=seq,digest=delivery.digest))
    return serialize(delivery)

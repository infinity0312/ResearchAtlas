"""Lossless provenance normalization and exhaustive plan diagnostics.

This cannot adjudicate scientific entailment. It never changes prose or values.
"""
import copy
from collections import Counter
from pydantic import ValidationError


def canonical_plan(raw, facts, blocks):
    value=copy.deepcopy(raw);changes=[]
    if not isinstance(value,dict):return value,changes
    def expand(ids,path):
        if not isinstance(ids,list):return ids
        result=[]
        for item in ids:
            mapped=facts[item]['evidence_ids'] if isinstance(item,str) and item in facts else [item]
            if mapped!=[item]:changes.append({'path':path,'alias':item,'sources':mapped})
            for source in mapped:
                if source not in result:result.append(source)
        if result!=ids:changes.append({'path':path,'before':ids,'after':result})
        return result
    for group in ['results','formulas','invariants']:
        for i,row in enumerate(value.get(group,[]) if isinstance(value.get(group),list) else []):
            if isinstance(row,dict):row['evidence_ids']=expand(row.get('evidence_ids'),f'{group}.{i}.evidence_ids')
    for i,row in enumerate(value.get('claims',[]) if isinstance(value.get('claims'),list) else []):
        if not isinstance(row,dict):continue
        primary=row.get('evidence_id');context=row.get('context_evidence_ids',[])
        if not isinstance(primary,str) or not isinstance(context,list):continue
        ids=expand([primary,*context],f'claims.{i}')
        if ids:
            row['evidence_id']=ids[0];row['context_evidence_ids']=ids[1:]
    # Redundant metadata is removable only if it agrees with explicit ownership.
    for i,row in enumerate(value.get('results',[]) if isinstance(value.get('results'),list) else []):
        if not isinstance(row,dict) or 'unit_id' not in row:continue
        units=value.get('units') if isinstance(value.get('units'),list) else []
        owners=[u.get('id') for u in units if isinstance(u,dict) and isinstance(u.get('result_ids'),list) and row.get('id') in u['result_ids']]
        if owners==[row['unit_id']]:
            changes.append({'path':f'results.{i}.unit_id','removed_redundant_owner':row.pop('unit_id')})
    return value,changes


def plan_diagnostics(raw,facts,blocks,topics):
    from .study_compiler import Plan
    errors=[]
    def issue(path,message):errors.append({'path':path,'message':message})
    try:Plan.model_validate(raw)
    except ValidationError as exc:
        for e in exc.errors():issue('.'.join(map(str,e['loc'])),e['msg'])
    if not isinstance(raw,dict):return errors
    def rows(name):
        v=raw.get(name,[])
        return [(i,r) for i,r in enumerate(v) if isinstance(r,dict)] if isinstance(v,list) else []
    def strings(v):return [x for x in v if isinstance(x,str)] if isinstance(v,list) else []
    def ids(name):return [r['id'] for _,r in rows(name) if isinstance(r.get('id'),str)]
    for name in ['units','results','formulas']:
        for key,count in Counter(ids(name)).items():
            if count>1:issue(name,f'Duplicate id {key}')
    for key,count in Counter(r['key'] for _,r in rows('invariants') if isinstance(r.get('key'),str)).items():
        if count>1:issue('invariants',f'Duplicate key {key}')
    for topic in strings(raw.get('topics')):
        if topic not in topics:issue('topics',f'Unknown topic {topic}; choose from {topics}')
    if {u.get('chapter') for _,u in rows('units') if type(u.get('chapter')) is int}!=set(range(5)):
        issue('units','All five chapters required')
    for i,u in rows('units'):
        refs=strings(u.get('fact_ids'))
        if len(refs)!=len(set(refs)):issue(f'units.{i}.fact_ids','Duplicate approved facts')
        for key in strings(u.get('fact_ids')):
            if key not in facts:issue(f'units.{i}.fact_ids',f'Unknown approved fact {key}')
        for field,group in [('result_ids','results'),('formula_ids','formulas')]:
            for key in strings(u.get(field)):
                if key not in ids(group):issue(f'units.{i}.{field}',f'Unknown {key}')
    for field,group in [('result_ids','results'),('formula_ids','formulas')]:
        owners=Counter(key for _,u in rows('units') for key in strings(u.get(field)))
        for key in ids(group):
            if owners[key]!=1:issue(group,f'{key} must have one owner, found {owners[key]}')
    for group in ['results','formulas','invariants','claims']:
        for i,row in rows(group):
            refs=[row.get('evidence_id'),*strings(row.get('context_evidence_ids'))] if group=='claims' else strings(row.get('evidence_ids'))
            for key in refs:
                if isinstance(key,str) and key not in blocks:issue(f'{group}.{i}',f'Unknown source {key}')
            refs=[x for x in refs if isinstance(x,str)]
            if len(refs)!=len(set(refs)):issue(f'{group}.{i}','Duplicate source IDs')
    for i,row in rows('results'):
        if row.get('value') is None and not row.get('unavailable_reason'):issue(f'results.{i}','Missing value requires reason')
        if row.get('value') is not None and row.get('unavailable_reason'):issue(f'results.{i}','Value conflicts with unavailable reason')
    return errors


def candidate_plan(raw,facts,blocks,topics,folder=None):
    from .study_compiler import Plan,check_plan
    from .study_protocol import checkpoint,digest
    normalized,changes=canonical_plan(raw,facts,blocks)
    errors=plan_diagnostics(normalized,facts,blocks,topics)
    if folder is not None:
        from pathlib import Path
        checkpoint(Path(folder)/'candidate.json',{'raw':raw,'normalized':normalized,'raw_sha256':digest(raw),'normalization':changes,'diagnostics':errors})
    if errors:
        import json
        raise ValueError(json.dumps(errors,ensure_ascii=False))
    return check_plan(Plan.model_validate(normalized),facts,blocks,topics)


class PlanInput:
    """Unapproved repair input; never accepted by the renderer or approval gate."""
    def __init__(self,raw):self.raw=copy.deepcopy(raw)
    def model_dump(self):return copy.deepcopy(self.raw)


def load_plan_input(folder):
    import json
    from pathlib import Path
    folder=Path(folder)
    if (folder/'plan.json').exists():return PlanInput(json.loads((folder/'plan.json').read_text('utf8')))
    candidate=json.loads((folder/'candidate.json').read_text('utf8'))
    return PlanInput(candidate['normalized'])

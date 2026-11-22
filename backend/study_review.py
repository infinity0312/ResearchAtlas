"""Mechanical contract for editor-reviewed evidence, not a semantic oracle.

Review files are editor-owned local inputs. Never populate them from an LLM's
claim that it has passed review. Production callers must authenticate the editor.
"""
import hashlib
from decimal import Decimal
from .llm_runtime import packed
from .study_protocol import evidence_context

FACETS={'problem','contributions','mechanism','experiments','limitations','context'}


def reviewed_context(inventory, blocks, review):
    if review.get('inventory_sha256')!=hashlib.sha256(packed(inventory).encode()).hexdigest():
        raise ValueError('Evidence review belongs to another inventory')
    if review.get('source_blocks_sha256')!=hashlib.sha256(packed(blocks).encode()).hexdigest():
        raise ValueError('Evidence review belongs to another source snapshot')
    if review.get('reviewer_kind') not in {'human','codex'} or not review.get('reviewer'):
        raise ValueError('Independent editor review is required')
    if review.get('status')!='approved' or review.get('blocking_issues')!=[]:
        raise ValueError('Evidence has unresolved blockers')
    available={f'u{u}:f{i}':fact for u,unit in enumerate(inventory['units']) for i,fact in enumerate(unit['facts'])}
    decisions=review.get('facts',[])
    selected=[];ids=set();seen=set()
    for item in decisions:
        key=item['id']
        if key in seen or key not in available:raise ValueError('Unknown or duplicate reviewed fact')
        seen.add(key)
        fact=available[key]
        if item.get('fact_sha256')!=hashlib.sha256(packed(fact).encode()).hexdigest():
            raise ValueError('Reviewed fact changed')
        if item.get('decision') not in {'approved','excluded','deferred'}:
            raise ValueError('Invalid editorial decision')
        if item['decision']!='approved':continue
        if not item.get('rationale'):raise ValueError('Missing evidence review rationale')
        if fact.get('needs_visual_review') and not item.get('visual_artifacts'):
            raise ValueError('Ambiguous figure/table requires visual review')
        for artifact in item.get('visual_artifacts',[]):
            from pathlib import Path
            p=Path(artifact['path'])
            if hashlib.sha256(p.read_bytes()).hexdigest()!=artifact['sha256']:
                raise ValueError('Visual evidence changed')
        selected.append({'id':key,**fact,'editor_note':item['rationale']})
        ids.update(fact['evidence_ids'])
    facets=review.get('facets',{})
    if set(facets)!=FACETS:raise ValueError('All core review facets must be accounted for')
    for name,facet in facets.items():
        if facet.get('status') not in {'covered','not_applicable'} or not facet.get('rationale'):
            raise ValueError('Unresolved core facet: '+name)
        if facet['status']=='covered' and not facet.get('evidence_ids'):
            raise ValueError('Covered facet requires source evidence')
        ids.update(facet.get('evidence_ids',[]))
    if not selected:raise ValueError('No approved facts')
    # Adjacent physical pages protect continued paragraphs, captions and equations.
    # The budget fails explicitly; it never silently slices the source.
    context=evidence_context(blocks,ids,max_chars=review.get('max_context_chars',160000))
    return selected,context


def numeric_comparison(left,right,operation):
    """Only compare like-for-like reviewed measurements; no model arithmetic."""
    for cell in (left,right):
        if cell.get('status')!='approved' or not cell.get('source'):
            raise ValueError('Numeric cells require approved source evidence')
    for field in ('task','metric','unit','protocol'):
        if not left.get(field) or left[field]!=right.get(field):
            raise ValueError('Incompatible measurement '+field)
    a,b=Decimal(str(left['value'])),Decimal(str(right['value']))
    if not a.is_finite() or not b.is_finite():raise ValueError('Non-finite measurement')
    if operation=='difference':return str(a-b)
    if operation=='relative_percent':
        if b==0:raise ValueError('Undefined relative change from zero baseline')
        return str((a-b)/b*100)
    raise ValueError('Unsupported comparison')

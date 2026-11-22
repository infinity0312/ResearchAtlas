"""Source context and immutable checkpoints for sequential study experiments.

These are mechanical gates, not semantic approval or an automatic publisher.
"""
import hashlib
import json
import os
import tempfile
from pathlib import Path


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf8')).hexdigest()


def checkpoint(path, value):
    """Idempotent exact replay; never replace an earlier experiment's result."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    # Publish a fully flushed file atomically without overwriting a competing
    # writer. A killed process may leave a temp file, never a partial checkpoint.
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',dir=path.parent,
                                         prefix='.'+path.name+'.',delete=False) as stream:
            temporary=Path(stream.name)
            stream.write(content);stream.flush();os.fsync(stream.fileno())
        try:os.link(temporary,path)
        except FileExistsError:
            if json.loads(path.read_text('utf8')) != value:
                raise ValueError('Checkpoint conflict; use a new experiment directory: ' + str(path))
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
    return path


def evidence_context(blocks, ids, explicit_pages=(), radius=1, max_chars=160000):
    """Retain adjacent physical pages, including table/paragraph continuations.

    This is a conservative window, not automatic table merging. Explicit pages
    must come from a resolved citation/section map. Unknown locations fail closed.
    """
    unknown = set(ids) - blocks.keys()
    if unknown:
        raise ValueError('Unknown evidence IDs: ' + ', '.join(sorted(unknown)))
    available = {b['page'] for b in blocks.values()}
    anchors = {blocks[i]['page'] for i in ids} | set(explicit_pages)
    if anchors - available:
        raise ValueError('Requested source pages are unavailable')
    wanted = {p + offset for p in anchors for offset in range(-radius, radius + 1)}
    result = {k: v for k, v in blocks.items() if v['page'] in wanted}
    if sum(len(b['text']) for b in result.values()) > max_chars:
        raise ValueError('Evidence context exceeds budget; split the verification unit, do not truncate')
    return result


def batch_readiness(manifest, results):
    """Require every pre-registered heldout, bound to a single frozen version.

    Results are editor-authored records, never accepted directly from an LLM.
    Caller remains responsible for authenticating the editor before publication.
    """
    required = manifest.get('heldout_paper_ids', [])
    errors = []
    if len(set(required)) < 3 or len(required) != len(set(required)):
        errors.append('At least three distinct pre-registered heldout papers are required')
    version = manifest.get('frozen_fingerprint')
    if not version:
        errors.append('Pipeline and skill must be frozen before heldout evaluation')
    if set(required) & set(manifest.get('development_paper_ids', [])):
        errors.append('Development papers cannot count as heldout')
    for paper in required:
        records = [r for r in results if r.get('paper_id') == paper]
        if len(records) != 1:
            errors.append(paper + ': missing or ambiguous evaluation')
            continue
        r = records[0]
        if r.get('fingerprint') != version:
            errors.append(paper + ': stale pipeline/skill')
        report = r.get('report_sha256')
        if not report or r.get('editorial_report_sha256') != report or not r.get('editorial_passed'):
            errors.append(paper + ': no independent approval of this report')
        if r.get('blocking_errors') != 0 or r.get('core_omissions') != 0:
            errors.append(paper + ': unresolved content defects')
        if r.get('editorial_content_changes') != 0:
            errors.append(paper + ': editor rewrites cannot count as model convergence')
        if not isinstance(r.get('repair_cycles'), int) or not 0 <= r['repair_cycles'] <= 2:
            errors.append(paper + ': repair budget not met')
        if not r.get('usage_complete'):
            errors.append(paper + ': incomplete cost record')
    return {'batch_allowed': not errors, 'reasons': errors}


def consecutive_readiness(manifest, results):
    """Ten consecutive independently accepted full reports, in registered order.

    Editor-owned records only. A failed/pending item or changed version cannot be
    skipped, deduplicated or silently combined with another experiment.
    """
    ordered=manifest.get('ordered_paper_ids',[])
    version=manifest.get('frozen_fingerprint')
    errors=[];streak=0
    if len(ordered)<10 or len(set(ordered))!=len(ordered):errors.append('Register at least ten distinct papers')
    if not version:errors.append('Frozen version required')
    if [r.get('paper_id') for r in results]!=ordered[:len(results)] or len(results)>len(ordered):errors.append('Cannot skip or reorder attempts')
    if set(ordered)&set(manifest.get('development_paper_ids',[])):errors.append('Development sample in acceptance sequence')
    for r in results:
        if r.get('fingerprint')!=version:errors.append('Version changed; start a new sequence')
        passed=(r.get('status')=='passed' and r.get('editorial_passed') is True
                and r.get('report_sha256') and r.get('editorial_report_sha256')==r['report_sha256']
                and r.get('source_complete') is True and r.get('math_passed') is True
                and r.get('blocking_errors')==0 and r.get('core_omissions')==0
                and r.get('editorial_content_changes')==0 and r.get('usage_complete') is True
                and type(r.get('repair_cycles')) is int and 0<=r['repair_cycles']<=2)
        streak=streak+1 if passed else 0
    return {'batch_allowed':not errors and streak>=10,'consecutive_passes':streak if not errors else 0,
            'target':10,'attempts':len(results),'reasons':errors}

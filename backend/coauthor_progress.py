"""Read-only projection of coauthor checkpoints; never exposes leases or prompts."""
import json
from pathlib import Path
from collections import Counter
from fastapi import APIRouter
from sqlalchemy import select
from .db import DATA,Session,Paper

router=APIRouter(prefix='/api/coauthor-batch')

def read(path,default):
    try:return json.loads(path.read_text('utf8'))
    except (OSError,ValueError):return default

def snapshot(root,titles):
    queue=read(root/'queue.json',{}).get('items',[])
    sources=read(root/'source-progress.json',{})
    rows=[]
    for item in queue:
        pid=item['paper_id'];source=sources.get(pid,{})
        status=source.get('status',item.get('status','queued'))
        error=''
        if status=='failed':error='证据提取未通过校验；检查点已保存，等待修复后继续'
        rows.append({'paper_id':pid,'title':titles.get(pid,pid),'route':item['route'],
                     'status':status,'tokens':item.get('tokens'), 'error':error,
                     'executor':'DeepSeek' if status in ('extracting','generating') else 'GPT / 人工' if status in ('evidence-ready','awaiting-gpt-review') else None})
    counts=dict(Counter(r['status'] for r in rows))
    timestamps=[p.stat().st_mtime for p in (root/'queue.json',root/'source-progress.json') if p.exists()]
    return {'items':rows,'total':len(rows),'counts':counts,'updated_at':max(timestamps,default=None),
            'blocked':counts.get('failed',0)>0 and not any(counts.get(s,0) for s in ('extracting','generating'))}

@router.get('')
def progress():
    with Session() as s:titles=dict(s.execute(select(Paper.id,Paper.title)).all())
    return snapshot(DATA/'coauthor-batch-20260929',titles)

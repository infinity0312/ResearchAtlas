"""Library completeness is measured, never inferred from task completion alone."""
import hashlib,json
from collections import Counter
from fastapi import APIRouter
from sqlalchemy import select
from .db import Session,Paper,Membership,Domain,Analysis,PaperTag,Job,DATA,now
from .analysis import compact
router=APIRouter(prefix='/api/library')

@router.get('/audit')
def audit():
    rows=[];totals=Counter();page_cache={}
    with Session() as s:
        domains={d.id:d for d in s.scalars(select(Domain))}
        papers={p.id:p for p in s.scalars(select(Paper))}
        latest={}
        for a in s.scalars(select(Analysis).order_by(Analysis.created.desc())):
            if a.paper_id in papers and a.domain_id in domains and a.version==papers[a.paper_id].version and a.taxonomy_version==domains[a.domain_id].taxonomy_version:latest.setdefault((a.paper_id,a.domain_id),a)
        tagged={r.paper_id for r in s.scalars(select(PaperTag).where(PaperTag.removed==False))}
        active={j.payload.get('paper_id'):j.status for j in s.scalars(select(Job).where(Job.status.in_(['running','queued']))) if not j.result.get('cancel_requested')}
        for m in s.scalars(select(Membership)):
            p=papers[m.paper_id];a=latest.get((p.id,m.domain_id));issues=[]
            pdf=DATA/'documents'/f'{hashlib.sha256(p.id.encode()).hexdigest()}v{p.version}.pdf'
            valid_pdf=False
            if pdf.exists():
                with pdf.open('rb') as f:valid_pdf=f.read(1024).lstrip().startswith(b'%PDF')
            if not valid_pdf:issues.append('missing_pdf')
            if not a:issues.append('missing_analysis')
            else:
                if a.content_hash not in page_cache:
                    path=DATA/'documents'/f'{a.content_hash}.json'
                    try:page_cache[a.content_hash]={x['page']:compact(x['text']) for x in json.loads(path.read_text('utf8'))}
                    except (OSError,ValueError,KeyError):page_cache[a.content_hash]={}
                pages=page_cache[a.content_hash]
                if not pages:issues.append('missing_parsed_text')
                claims=a.result.get('claims',[])
                if not claims or any(not c.get('quote') or compact(c['quote']) not in pages.get(c.get('page'),'') for c in claims):issues.append('unverified_evidence')
                if not a.result.get('methods'):issues.append('missing_methods')
                if p.id not in tagged:issues.append('missing_tags')
            totals['pairs']+=1;totals['ready' if not issues else 'incomplete']+=1
            totals.update(issues)
            rows.append({'paper_id':p.id,'domain_id':m.domain_id,'domain':domains[m.domain_id].name,'title':p.title,'analysis_id':a.id if a else None,'issues':issues,'task':active.get(p.id)})
    return {'generated':now(),'papers':len(papers),'totals':dict(totals),'items':rows,'scope':'本地文库及当前论文/分类版本；宏观趋势数据独立核验'}

"""Publish a reviewed agent packet through source- and revision-checked APIs.

Run only after editorial review. Validation verifies source integrity, not the
scientific correctness of every inference. No model calls and no direct DB edits.
"""
import argparse,json,shutil,subprocess,tempfile
from pathlib import Path
import httpx
from backend.contracts import Extraction
from backend.analysis import verified_claims

def publish(packet_path):
    path=Path(packet_path);packet=json.loads(path.read_text('utf8'))
    report=Path(packet['draft_path']).read_text('utf8')
    raw=json.loads(Path(packet['result_path']).read_text('utf8'))
    result=Extraction.model_validate(raw.get('result',raw)).model_dump()
    node=shutil.which('node') or str(Path('F:/dev/node/node.exe'))
    # Validate the exact report and structured presentation that will be sent to
    # Atlas. Original packet/result files remain unchanged.
    with tempfile.TemporaryDirectory(prefix='atlas-fulltext-math-') as temporary:
        math_input=Path(temporary)/'analysis.json'
        math_input.write_text(json.dumps({'result':{**result,'fulltext_markdown':report}},ensure_ascii=False),encoding='utf8')
        math_check=subprocess.run([node,'scripts/validate_fulltext_math.mjs',str(math_input),'--analysis'],capture_output=True,text=True,encoding='utf8')
    if math_check.returncode:raise ValueError('Math rendering validation failed: '+math_check.stdout.strip())
    pages=json.loads((Path('data/documents')/(packet['content_hash']+'.json')).read_text('utf8'))
    if len(report.strip())<1000:raise ValueError('Report missing substantive full-text review')
    if not result['claims'] or len(verified_claims(result['claims'],pages))!=len(result['claims']):raise ValueError('Evidence quote/page mismatch')
    if not set(packet['reviewed_pages'])<={p['page'] for p in pages}:raise ValueError('Invalid coverage pages')
    c=httpx.Client(base_url='http://127.0.0.1:8765/api',headers={'X-Atlas-Client':'1'},timeout=120)
    domains=c.get('/domains');domains.raise_for_status()
    domain=next((d for d in domains.json() if d['id']==packet['domain_id']),None)
    if not domain:raise ValueError('Unknown publication domain')
    if not result['methods'] or not result['topics']:raise ValueError('Methods and valid domain topics are required')
    invalid=set(result['topics'])-set(domain['topics'])
    if invalid:raise ValueError('Topics outside domain taxonomy: '+', '.join(sorted(invalid)))
    paper=c.get('/paper',params={'id':packet['paper_id']});paper.raise_for_status()
    if packet['domain_id'] not in paper.json()['domain_ids']:raise ValueError('Paper does not belong to publication domain')
    work=next(w for w in c.get('/collaboration').json() if w['id']==packet['work_id'])
    if work['status']=='published':return {'already_published':True,'analysis_id':work.get('analysis_id')}
    if work['status']!='review' or work['revision']!=packet['review_revision']:raise ValueError('Review revision changed')
    if work['paper_ids']!=[packet['paper_id']] or work['markdown'].strip()!=report.strip():raise ValueError('Reviewed draft differs from submitted report')
    context=c.get('/collaboration/context',params={'paper_id':packet['paper_id'],'page_start':1,'page_end':1});context.raise_for_status()
    if context.json()['fingerprint']!=work['base']:raise ValueError('Base changed; merge the draft before publishing')
    lease=c.post('/collaboration/'+work['id']+'/claim',json={'owner':packet.get('review_owner','codex-editor')});lease.raise_for_status();lease=lease.json()
    # Keep the private checkout recoverable if the HTTP publication fails.
    # This file is local only; never include it in reports or tool output.
    path.with_suffix('.lease.json').write_text(json.dumps(lease,ensure_ascii=False,indent=2),'utf8')
    body={k:packet[k] for k in ['domain_id','content_hash','reviewed_pages']}
    body.update(token=lease['lease_token'],revision=lease['revision'],result=result,fulltext_markdown=report,review_model=packet.get('review_model','codex'))
    if packet.get('generation_model'):body['generation_model']=packet['generation_model']
    response=c.post('/collaboration/'+work['id']+'/publish-analysis',json=body);response.raise_for_status()
    receipt=response.json();path.with_suffix('.published.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
    return {'paper_id':packet['paper_id'],'analysis_id':receipt['analysis_id'],'reviewed_pages':len(packet['reviewed_pages']),'claims':len(result['claims'])}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('packet');args=p.parse_args()
    print(json.dumps(publish(args.packet),ensure_ascii=False))

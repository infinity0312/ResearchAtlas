"""Local JSON CLI. No model calls or database writes outside the app API."""
import argparse,json,urllib.request,urllib.parse,urllib.error
from pathlib import Path
BASE='http://127.0.0.1:8765/api'
def call(path,method='GET',data=None):
    req=urllib.request.Request(BASE+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers={'X-Atlas-Client':'1','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=120) as r:return json.load(r)
    except urllib.error.HTTPError as exc:
        try:detail=json.load(exc)
        except ValueError:detail={'detail':str(exc)}
        raise SystemExit(json.dumps({'status':exc.code,**detail},ensure_ascii=False)) from None
def main():
    p=argparse.ArgumentParser(description='Research Atlas 人 / DeepSeek / Codex 协作接口');sub=p.add_subparsers(dest='cmd',required=True)
    sub.add_parser('status');sub.add_parser('sync');sub.add_parser('jobs')
    a=sub.add_parser('search');a.add_argument('query')
    a=sub.add_parser('context');a.add_argument('paper_id');a.add_argument('--start',type=int,default=1);a.add_argument('--end',type=int,default=5)
    a=sub.add_parser('create');a.add_argument('--title',required=True);a.add_argument('--instruction',required=True);a.add_argument('--paper',action='append',default=[]);a.add_argument('--kind',default='review',choices=['review','curation','synthesis','derivation'])
    a=sub.add_parser('checkout');a.add_argument('id');a.add_argument('--owner',default='codex');a.add_argument('--directory',required=True)
    for command in ('submit','heartbeat'):
        a=sub.add_parser(command);a.add_argument('directory')
    a=sub.add_parser('publish');a.add_argument('id');a.add_argument('--revision',type=int,required=True)
    args=p.parse_args()
    if args.cmd=='status':result=call('/collaboration')
    elif args.cmd=='jobs':result=call('/jobs')
    elif args.cmd=='sync':result=call('/workspace/sync','POST',{})
    elif args.cmd=='search':result=call('/papers?'+urllib.parse.urlencode({'q':args.query,'days':0,'size':30}))
    elif args.cmd=='context':result=call('/collaboration/context?'+urllib.parse.urlencode({'paper_id':args.paper_id,'page_start':args.start,'page_end':args.end}))
    elif args.cmd=='create':result=call('/collaboration','POST',{'title':args.title,'instruction':args.instruction,'paper_ids':args.paper,'kind':args.kind})
    elif args.cmd=='checkout':
        d=Path(args.directory);d.mkdir(parents=True,exist_ok=True)
        if any((d/name).exists() for name in ('lease.json','draft.md','context.json')):raise SystemExit('目录已有协作草稿，请使用另一个目录，避免覆盖')
        lease=call('/collaboration/'+args.id+'/claim','POST',{'owner':args.owner})
        (d/'lease.json').write_text(json.dumps(lease,ensure_ascii=False,indent=2),encoding='utf8')
        (d/'draft.md').write_text(lease.get('markdown') or '# '+lease['title']+'\n\n',encoding='utf8')
        contexts=[call('/collaboration/context?'+urllib.parse.urlencode({'paper_id':pid})) for pid in lease['paper_ids']]
        (d/'context.json').write_text(json.dumps(contexts,ensure_ascii=False,indent=2),encoding='utf8')
        result={'directory':str(d.resolve()),'revision':lease['revision'],'lease_until':lease['lease_until']}
    elif args.cmd in ('submit','heartbeat'):
        d=Path(args.directory);lease=json.loads((d/'lease.json').read_text('utf8'))
        result=call('/collaboration/'+lease['id']+('/heartbeat' if args.cmd=='heartbeat' else ''),'POST' if args.cmd=='heartbeat' else 'PUT',{'token':lease['lease_token'],'revision':lease['revision'],'markdown':(d/'draft.md').read_text('utf8')})
    else:result=call('/collaboration/'+args.id+'/publish','POST',{'revision':args.revision})
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

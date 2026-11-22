"""Isolated workload: never inserts benchmark data into the user's library."""
import os,tempfile,json,time,statistics
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
os.environ['ATLAS_DATA']=tempfile.mkdtemp(prefix='atlas-benchmark-')
from backend.db import *
from backend.app import app
from fastapi.testclient import TestClient
init_db()
with Session.begin() as s:
    for i in range(10000):
        pid=f'2609.{i:05d}'
        s.add(Paper(id=pid,version=1,title=f'Molecular learning benchmark paper {i}',abstract='Prediction of scientific properties with an equivariant neural network. '*10,authors=['Test Author'],categories=['cs.LG'],published=now(),updated=now()))
        s.add(Membership(domain_id='molecules',paper_id=pid))
        if i<1000:s.add(Analysis(paper_id=pid,domain_id='molecules',version=1,taxonomy_version=1,model='fixture',content_hash='fixture',result={'topics':['性质预测'],'methods':['GNN'],'summary':'Benchmark fixture','claims':[{'text':'fixture','page':1,'quote':'fixture'}]*6}))
def measure(path):
    with TestClient(app) as client:
        for _ in range(5):assert client.get(path).status_code==200
        def once(_):
            begin=time.perf_counter();r=client.get(path);assert r.status_code==200;return (time.perf_counter()-begin)*1000
        with ThreadPoolExecutor(max_workers=5) as pool: times=list(pool.map(once,range(100)))
    return {'samples':len(times),'concurrency':5,'p50_ms':round(statistics.median(times),2),'p95_ms':round(sorted(times)[94],2),'max_ms':round(max(times),2)}
report={'metadata':10000,'analyses':1000,'transport':'in-process ASGI; excludes network and browser; no active PDF worker','results':{p:measure(p) for p in ['/api/papers?domain_id=molecules','/api/papers?q=equivariant','/api/overview?domain_id=molecules','/api/papers?domain_id=molecules&topic=性质预测']}}
out=ROOT/'docs'/'benchmark.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True))

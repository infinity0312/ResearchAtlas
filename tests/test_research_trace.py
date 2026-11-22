import hashlib
import json

from fastapi.testclient import TestClient

from backend.app import app
from backend.db import Analysis, DATA, Paper, Session, now


def test_trace_reports_artifacts_and_missing_evidence_for_exact_analysis():
    client = TestClient(app)
    paper_id = '2401.00001'
    content_hash = hashlib.sha256(b'trace bytes').hexdigest()
    quote = 'Evidence appears in the original first page.'
    docs = DATA / 'documents'
    docs.mkdir(exist_ok=True)
    (docs / f'{content_hash}.json').write_text(
        json.dumps([{'page':1,'text':quote}]), encoding='utf-8',
    )
    with Session.begin() as s:
        for pid in (paper_id, '2401.00002'):
            s.add(Paper(id=pid, title='Fixture', abstract='', version=2, published=now(), updated=now()))
        a = Analysis(paper_id=paper_id, domain_id='ml', taxonomy_version=1, version=1,
                     model='recorded generation model', content_hash=content_hash, result={
                         'pages':1, 'fulltext_markdown':'## 研究问题与核心贡献\n内容说明',
                         'claims':[{'page':1,'quote':quote},{'page':2,'quote':quote}],
                     })
        s.add(a)
        s.flush()
        aid = a.id
    path = '/api/paper/research-trace'
    record = client.get(path, params={'id':paper_id,'version':1,'analysis_id':aid}).json()
    assert record['paper_version']==1 and record['parsed_pages']==1
    assert not record['pdf_available']
    assert record['analysis']['recorded_model']=='recorded generation model'
    assert record['analysis']['quotes_located']==1
    assert record['analysis']['report_sections']==['研究问题与核心贡献']
    assert not record['analysis']['reviewers'] and record['analysis']['quality']['freshness']=='stale'
    assert client.get(path,params={'id':paper_id,'version':2,'analysis_id':aid}).status_code==404
    assert client.get(path,params={'id':'2401.00002','version':1,'analysis_id':aid}).status_code==404
    assert client.get(path,params={'id':paper_id,'version':2}).json()['analysis'] is None

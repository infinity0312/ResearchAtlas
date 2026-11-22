import pytest
from backend.macro_coauthor import validate_candidate,validate_editorial,candidate_hash,EditorialReview,CHECKS

def fixture():
 source={'source_hash':'source-v1','papers':[{'id':'a','passages':['A method.','Scaling remains unresolved.']} ]}
 rows=[dict(id='a',novelty=50,rigor=60,headroom=None,headroom_evidence=None,family='Transformer',bottleneck='证据不足，保留空值',evidence_index=0)]
 review=EditorialReview(reviewer='gpt-sol',source_hash='source-v1',candidate_hash=candidate_hash(rows),papers=[dict(id='a',checks=sorted(CHECKS),note='已逐项核对范围与证据；未提供可量化剩余空间依据，保留空值。')])
 return source,rows,review

def test_editorial_binds_exact_source_and_candidate():
 source,rows,review=fixture();validate_editorial(source,rows,review)
 rows[0]['novelty']=99
 with pytest.raises(ValueError):validate_editorial(source,rows,review)
 source,rows,review=fixture();source['source_hash']='new'
 with pytest.raises(ValueError):validate_editorial(source,rows,review)

def test_all_papers_and_checks_required():
 source,rows,review=fixture()
 with pytest.raises(ValueError):validate_candidate(source,rows*2)
 review.papers[0].checks=['source']
 with pytest.raises(ValueError):validate_editorial(source,rows,review)
 rows[0]['headroom']=70
 with pytest.raises(ValueError):validate_candidate(source,rows)
 rows[0]['headroom_evidence']=8
 with pytest.raises(ValueError):validate_candidate(source,rows)

def test_prepare_is_idempotent():
 from backend.macro_coauthor import prepare
 source,_,_=fixture();source.update(name='Sample',year=2025)
 root,one=prepare(source);_,two=prepare(source)
 assert one['work_id']==two['work_id']
 assert one['status']=='queued'

def test_api_coauthor_cannot_bypass_editorial_gate():
 from fastapi.testclient import TestClient
 from backend.app import app
 from backend.db import Session,TrendSeries,CatalogPaper,SearchSnapshot,TrendEvidence
 c=TestClient(app);headers={'X-Atlas-Client':'1'}
 with Session.begin() as s:
  s.add(TrendSeries(id='macro-gate',name='Gate',query='cat:cs.LG',color='#123456'))
  s.add(CatalogPaper(id='a',metadata_json={'id':'a','title':'Model','abstract':'A method. Scaling remains unresolved.','published':'2025-02-01'}))
  s.add(SearchSnapshot(key='macro-gate-index',query='cat:cs.LG',start='2025-01-01',end='2025-12-31',paper_ids=['a'],source='test',complete=True))
 prepared=c.post('/api/trends/coauthor-prepare',json={'series_id':'macro-gate','year':2025},headers=headers).json()
 source=c.get('/api/trends/review-packet?series_id=macro-gate&year=2025').json()
 lease=c.post('/api/collaboration/'+prepared['work_id']+'/claim',json={'owner':'gpt-review'},headers=headers).json()
 _,rows,_=fixture()
 body=dict(work_id=prepared['work_id'],token=lease['lease_token'],revision=lease['revision'],series_id='macro-gate',year=2025,source_hash=source['source_hash'],papers=rows)
 assert c.post('/api/trends/publish-review',json=body,headers=headers).status_code==422
 body['pipeline']='macro-coauthor-v1'
 assert c.post('/api/trends/publish-review',json=body,headers=headers).status_code==422
 body['editorial_review']=dict(reviewer='gpt-sol',source_hash=source['source_hash'],candidate_hash=candidate_hash(rows),papers=[dict(id='a',checks=sorted(CHECKS),note='范围、方法与剩余瓶颈已对照原文；不足以量化创新空间。')])
 response=c.post('/api/trends/publish-review',json=body,headers=headers)
 assert response.status_code==200,response.text
 with Session() as s:
  result=s.get(TrendEvidence,response.json()['trend_review_key']).result
  assert result['provenance']['source']=='deepseek-draft-gpt-review'

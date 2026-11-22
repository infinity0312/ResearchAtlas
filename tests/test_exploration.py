from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app import app
from backend.db import *
from backend.history import branches,parse_search,collect
from backend.exploration import pick_months,rate_batch,run_exploration,month_windows
from sqlalchemy import select,func
import pytest
c=TestClient(app);H={'X-Atlas-Client':'1'}
HTML='''<h1 class="title">Showing 1&ndash;1 of 1 results</h1><li class="arxiv-result"><p class="list-title"><a>arXiv:2501.00001</a></p><div class="tags"><span class="tag">cs.LG</span></div><p class="title">Graph model</p><p class="authors"><a>Researcher</a></p><span class="abstract-full" id="2501.00001v2-abstract-full">We validate a graph method on large datasets.<a>Less</a></span><p class="is-size-7">Submitted 7 February, 2025; v1 submitted 2 January, 2025; originally announced January 2025.</p></li>'''
def paper(i=1,month='2025-01'):
 return {'id':f'2501.{i:05d}','version':1,'title':'Graph model','abstract':'We validate a graph method on large datasets.','authors':[],'categories':['cs.LG'],'published':month+'-02T00:00:00+00:00','updated':month+'-02T00:00:00+00:00','date_basis':'submitted'}
def config():return {'target':3,'maximum':6,'threshold':70,'exceptional':85}
def test_query_branches_keep_boolean_semantics():
 b=branches('(cat:cs.LG OR cat:q-bio.BM) AND (abs:"graph neural" OR ti:protein)')
 assert len(b)==4 and all(len(x)==2 for x in b)
 assert branches('ti:protein ANDNOT (abs:review OR abs:survey)')==[[('ti:protein',False),('abs:review',True),('abs:survey',True)]]
 with pytest.raises(ValueError):branches('broken:query')
def test_search_parser_uses_first_submission_and_preserves_version():
 rows,total=parse_search(HTML);assert total==1
 assert rows[0]['published'].startswith('2025-01-02') and rows[0]['updated'].startswith('2025-02-07') and rows[0]['version']==2
 assert rows[0]['abstract']=='We validate a graph method on large datasets.'
 with pytest.raises(ValueError):parse_search('<h1>Invalid</h1>')
 assert parse_search('<h1>Sorry, your query returned no results</h1>')==([],0)
def test_full_metadata_union_cached_without_filling_local_library():
 with patch('backend.history.search_page',side_effect=[([paper(1),paper(2)],2),([paper(2),paper(3)],2)]) as remote:
  rows,k=collect('ti:graph OR abs:graph','2025-01-01','2025-01-31');assert len(rows)==3 and remote.call_count==2
  again,_=collect('ti:graph OR abs:graph','2025-01-01','2025-01-31');assert len(again)==3 and remote.call_count==2
  subset,_=collect('ti:graph OR abs:graph','2025-01-01','2025-01-15');assert len(subset)==3 and remote.call_count==2
 with Session() as s:
  assert s.scalar(select(func.count()).select_from(Paper))==0
  assert s.scalar(select(func.count()).select_from(CatalogPaper))==3
  assert s.get(SearchSnapshot,k).complete

def test_incomplete_pagination_never_becomes_complete_snapshot():
 with patch('backend.history.search_page',side_effect=[([paper(1)],2),([paper(1)],2)]):
  with pytest.raises(ValueError):collect('ti:graph','2025-01-01','2025-01-31')
 with Session() as s:assert s.scalar(select(func.count()).select_from(SearchSnapshot))==0

def test_quality_selection_not_a_quota_and_extra_high_quality():
 ps=[paper(i) for i in range(7)]+[paper(8,'2025-02')]
 scores=[92,91,88,86,80,69,40,30];rs={p['id']:{'score':v,'relevance':90} for p,v in zip(ps,scores)}
 selected=pick_months(ps,rs,config());assert [r['id'] for r in selected]==[ps[i]['id'] for i in range(4)]
 rs[ps[0]['id']]['relevance']=10;assert ps[0] not in pick_months(ps,rs,config())
 assert pick_months([ps[-1]],rs,config())==[]
def test_rank_requires_every_id_and_verifiable_evidence():
 class Model:
  def generate(self,prompt):return {'papers':[{'id':'2501.00001','relevance':90,'novelty':80,'rigor':80,'impact':80,'reason':'Strong validation evidence','quote':'We validate a graph method'}]}
 assert rate_batch([paper()],[],Model())['2501.00001']['score']==80
 with pytest.raises(ValueError):rate_batch([paper(),paper(2)],[],Model())
def test_statistics_only_workflow_and_dependency_validation():
 payload={'domain_ids':['molecules'],'start':'2025-01-01','end':'2025-01-31','steps':['statistics']}
 r=c.post('/api/exploration',headers=H,json=payload);assert r.status_code==202
 with Session() as s:j=s.get(Job,r.json()['job_id'])
 with patch('backend.exploration.collect',return_value=([paper()],'snapshot')):result=run_exploration(j,lambda *args:None)
 assert result['catalog_count']==1 and result['selected']==[]
 with Session() as s:
  assert s.scalar(select(func.count()).select_from(TrendCount))==1
  assert s.scalar(select(func.count()).select_from(Paper))==0
 assert c.post('/api/exploration',headers=H,json={**payload,'start':'2025-02-01'}).status_code==422
 assert c.post('/api/exploration',headers=H,json={**payload,'maximum':1}).status_code==422
 assert list(month_windows('2024-02-15','2024-03-02'))==[('2024-02','2024-02-15','2024-02-29'),('2024-03','2024-03-01','2024-03-02')]

def test_full_workflow_resumes_without_repeating_ranking_download_or_analysis():
 from types import SimpleNamespace
 from backend.analysis import PROMPT_VERSION
 payload={'domain_ids':['molecules'],'start':'2025-01-01','end':'2025-01-31','steps':['search','fetch','analyze','statistics']}
 with patch('backend.exploration.get_key',return_value='configured'):
  r=c.post('/api/exploration',headers=H,json=payload)
 with Session() as s:j=s.get(Job,r.json()['job_id'])
 score={'2501.00001':{'id':'2501.00001','score':80,'relevance':90,'reason':'validated','quote':'We validate a graph method'}}
 def download(pid,v,path):path.write_bytes(b'fixture')
 def analyze(child):
  from backend.analysis_repository import provider_fingerprint
  bound={'text':'Graph method','claim_ids':['c1']}
  result={'prompt_version':PROMPT_VERSION,'pipeline_fingerprint':provider_fingerprint(SimpleNamespace(config={'model':'fixture'})),
          'summary':'Graph method','topics':[],'methods':['Graph method'],'problems':[],
          'claims':[{'id':'c1','kind':'method','text':'Graph method','page':1,'quote':'We validate a graph method'}],
          'grounding':{'summary':[bound],'topics':[],'methods':[bound],'problems':[]}}
  with Session.begin() as s:s.add(Analysis(paper_id=child.payload['paper_id'],domain_id='molecules',version=1,taxonomy_version=1,model='fixture',content_hash='fixture',result=result))
  return {'message':'done'}
 with patch('backend.exploration.collect',return_value=([paper()],'snapshot')),patch('backend.exploration.DeepSeek',return_value=SimpleNamespace(config={'model':'fixture'})),patch('backend.exploration.rate_batch',return_value=score) as rank,patch('backend.exploration.download_pdf',side_effect=download) as pdf,patch('backend.exploration.parse_pdf',return_value=([],'fixture')),patch('backend.worker.run_job',side_effect=analyze) as analysis:
  first=run_exploration(j,lambda *a:None);second=run_exploration(j,lambda *a:None)
  assert first['analyzed']==1 and second['skipped_analyses']==1
  assert rank.call_count==1 and pdf.call_count==1 and analysis.call_count==1
 with Session() as s:assert s.scalar(select(func.count()).select_from(Paper))==1

def test_daily_budget_yields_resumable_wait_instead_of_skipping_selected_papers():
 from types import SimpleNamespace
 with Session.begin() as s:
  cfg=s.get(Setting,'llm');cfg.value={**cfg.value,'daily_limit':1}
  s.add(Job(id='used-budget',kind='analyze',payload={},status='done'))
 with patch('backend.exploration.get_key',return_value='configured'):
  response=c.post('/api/exploration',headers=H,json={'domain_ids':['molecules'],'start':'2025-01-01','end':'2025-01-31'})
 with Session() as s:j=s.get(Job,response.json()['job_id'])
 score={'2501.00002':{'id':'2501.00002','score':90,'relevance':90,'reason':'validated','quote':'We validate a graph method'}}
 with patch('backend.exploration.collect',return_value=([paper(2)],'snapshot')),patch('backend.exploration.DeepSeek',return_value=SimpleNamespace(config={'model':'fixture'})),patch('backend.exploration.rate_batch',return_value=score),patch('backend.exploration.download_pdf',side_effect=lambda pid,v,path:path.write_bytes(b'fixture')),patch('backend.exploration.parse_pdf',return_value=([],'fixture')),patch('backend.worker.run_job') as analysis:
  result=run_exploration(j,lambda *a:None)
  assert result['stage']=='awaiting_budget' and result['resume_after']>now() and len(result['selected'])==1
  analysis.assert_not_called()

def test_indexed_evidence_is_copied_from_original_and_invalid_index_is_rejected():
 class Model:
  def __init__(self,index):self.index=index
  def generate(self,prompt):return {'papers':[{'id':'2501.00001','relevance':90,'novelty':80,'rigor':80,'impact':80,'reason':'Strong validation evidence','evidence_index':self.index}]}
 rated=rate_batch([paper()],[],Model(0))
 assert rated['2501.00001']['quote']==paper()['abstract']
 with pytest.raises(ValueError):rate_batch([paper()],[],Model(3))

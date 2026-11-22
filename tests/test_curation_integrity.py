from tests.test_trends_graph import c,H,seed

def test_metadata_revision_and_immutable_analysis():
 seed();route='/api/paper/metadata?id=2609.00001'
 original=c.get(route).json()
 body={'revision':original['revision'],'abstract':'Source abstract','authors':['A. Author'],'source':'https://arxiv.org/abs/2609.00001','evidence':'Checked original PDF title page and abstract.'}
 changed=c.put(route,headers=H,json=body);assert changed.status_code==200,changed.text
 assert changed.json()['version']==original['version']
 assert c.put(route,headers=H,json=body).status_code==409
 assert c.get('/api/method-matrix').json()['papers'][0]['families']==['图神经网络']

def test_method_substrings_are_not_acronyms():
 from backend.method_families import family,EXCLUDED
 assert family('unrecognized',{})=='待归类'
 assert family('MAE',{})==EXCLUDED
 assert family('masked autoencoder',{})!=EXCLUDED
 assert family('search space',{})!='等变网络 / 原子势'
 assert family('TripletsNet',{})!='量化 / 模型压缩'
 assert family('GNN',{'GNN':'用户分类'})=='用户分类'


def test_direction_sync_is_idempotent_and_preserves_custom_query():
 from backend.db import Session,Domain,TrendSeries
 from backend.topic_catalog import sync_directions
 with Session.begin() as s:
  s.add(Domain(id='medical',name='医疗',query='cat:cs.CV',topics=['医学影像与分割']))
 sync_directions()
 with Session() as s:assert s.get(Domain,'medical').definitions[0]['definition']
 rows=c.get('/api/trends/series').json()
 row=next(x for x in rows if x['name']=='医学影像与分割');assert row['domain_id']=='medical'
 c.put('/api/trends/series/'+row['id'],headers=H,json={'name':row['name'],'query':'ti:custom','domain_id':'medical'})
 sync_directions();again=c.get('/api/trends/series').json()
 assert len(again)==len(rows)
 assert next(x for x in again if x['id']==row['id'])['query']=='ti:custom'

def test_out_of_scope_samples_cannot_inflate_opportunity():
 from backend.trend_signals import summarize
 rows=[{'headroom':80,'novelty':80,'rigor':70,'family':'GNN','relevant':True} for _ in range(7)]
 rows.append({'headroom':100,'novelty':100,'rigor':100,'family':'GNN','relevant':False})
 result=summarize({'papers':rows,'sample':8})
 assert result['opportunity'] is None
 assert result['sample']==7 and result['excluded_count']==1

def test_fulltext_source_is_bound_to_sample_and_changes_revision(monkeypatch):
 import httpx
 from backend.db import Session,TrendSeries,SearchSnapshot,CatalogPaper
 with Session.begin() as s:
  s.add(TrendSeries(id='fulltext',name='Test',query='ti:test',color='#000000'))
  s.add(CatalogPaper(id='2501.12345',metadata_json={'id':'2501.12345','title':'Test','abstract':'We evaluated a model.','published':'2025-01-02'}))
  s.add(SearchSnapshot(key='fulltext',query='ti:test',start='2025-01-01',end='2025-12-31',paper_ids=['2501.12345'],source='test',complete=True))
 route='/api/trends/review-packet?series_id=fulltext&year=2025';before=c.get(route).json()
 assert c.post('/api/trends/review-source?series_id=fulltext&year=2025&paper_id=2501.00000',headers=H).status_code==422
 html='<section id="limits"><h2>Limitations</h2><p>Our model still fails to generalize to larger molecules and requires further evaluation.</p></section>'
 monkeypatch.setattr(httpx,'get',lambda *a,**k:httpx.Response(200,text=html,request=httpx.Request('GET','https://arxiv.org/html/2501.12345')))
 r=c.post('/api/trends/review-source?series_id=fulltext&year=2025&paper_id=2501.12345',headers=H);assert r.status_code==200,r.text
 after=c.get(route).json();assert before['source_hash']!=after['source_hash']
 assert after['papers'][0]['passage_sources'][1]['url'].endswith('#limits')
 assert len(before['papers'][0]['passages'])==1

def test_pdf_review_source_requires_matching_sample_hash_page_and_quote(monkeypatch):
 import hashlib,json
 from backend.db import DATA,Session,TrendSeries,SearchSnapshot,CatalogPaper
 from backend import analysis
 pid='2501.12345';quote='The single GPU is still a memory bottleneck for this system.'
 with Session.begin() as s:
  s.add(TrendSeries(id='pdf-review',name='PDF',query='ti:pdf',color='#000000'))
  s.add(CatalogPaper(id=pid,metadata_json={'id':pid,'title':'PDF','abstract':'A tested system.','published':'2025-01-02'}))
  s.add(SearchSnapshot(key='pdf-review',query='ti:pdf',start='2025-01-01',end='2025-12-31',paper_ids=[pid],source='test',complete=True))
 root=DATA/'macro-evidence'/'sources';root.mkdir(parents=True,exist_ok=True)
 path=root/(hashlib.sha256(pid.encode()).hexdigest()+'.pdf');path.write_bytes(b'%PDF test fixture')
 h=hashlib.sha256(path.read_bytes()).hexdigest()
 path.with_suffix('.json').write_text(json.dumps({'id':pid,'content_hash':h,'source_url':'https://arxiv.org/pdf/'+pid+'v1'}),'utf8')
 monkeypatch.setattr(analysis,'parse_pdf',lambda _:([{'page':7,'text':quote}],h))
 route='/api/trends/review-packet?series_id=pdf-review&year=2025';before=c.get(route).json()
 body={'series_id':'pdf-review','year':2025,'paper_id':pid,'source_hash':before['source_hash'],'content_hash':h,'passages':[{'page':7,'text':quote}]}
 post=lambda b:c.post('/api/trends/review-source-pdf',headers=H,json=b)
 assert post({**body,'content_hash':'0'*64}).status_code==409
 assert post({**body,'passages':[{'page':6,'text':quote}]}).status_code==422
 assert post({**body,'passages':[{'page':7,'text':quote+' Fabricated claim.'}]}).status_code==422
 assert post(body).status_code==200
 after=c.get(route).json();assert after['source_hash']!=before['source_hash']
 assert after['papers'][0]['passage_sources'][1]['url'].endswith('#page=7')
 assert post(body).status_code==409


def test_automatic_tag_reconciliation_preserves_manual_and_user_removal():
 from backend.db import Session,PaperTag,Tag,Analysis
 from backend.tags import import_result,reconcile_paper
 from sqlalchemy import select
 seed()
 with Session.begin() as s:
  import_result(s,'2609.00001',{'topics':['old'], 'methods':['GNN']})
  manual=Tag(name='personal',normalized='personal',kind='custom');s.add(manual);s.flush();s.add(PaperTag(paper_id='2609.00001',tag_id=manual.id,source='manual'))
  a=s.scalar(select(Analysis));a.result={'topics':['new'],'methods':['GNN']}
  old=s.scalar(select(Tag).where(Tag.name=='old'));old_id=old.id
  reconcile_paper(s,'2609.00001');s.flush()
  assert s.get(PaperTag,('2609.00001',old_id)) is None
  assert s.get(PaperTag,('2609.00001',manual.id)).source=='manual'
  tag=s.scalar(select(Tag).where(Tag.name=='GNN'));link=s.get(PaperTag,('2609.00001',tag.id));link.removed=True
  reconcile_paper(s,'2609.00001');assert link.removed


def test_method_families_are_idempotent():
 from backend.method_families import RULES,REVIEWED_GROUPS,family
 for name in {x[0] for x in RULES}|set(REVIEWED_GROUPS):
  assert family(name,{})==name


def test_unexecutable_queries_are_rejected_before_enqueuing():
 from backend.topic_catalog import CATALOG
 from backend.history import branches
 for item in CATALOG:assert branches(item['query'])
 query=' AND '.join('(abs:a OR abs:b)' for _ in range(7))
 r=c.post('/api/trends/series',headers=H,json={'name':'Invalid','query':query})
 assert r.status_code==422
 assert not any(x['name']=='Invalid' for x in c.get('/api/trends/series').json())

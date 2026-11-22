from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app import app
from backend.db import *
from backend.query_identity import query_identity
from backend.trend_identity import migrate_series,ensure_scope
from backend.services import enqueue
from backend.trends import key
from backend.history import collect
from sqlalchemy import select,func
client=TestClient(app);H={'X-Atlas-Client':'1'}
def test_equivalence_preserves_boolean_meaning():
 assert query_identity('((ti:a OR abs:"two words"))')==query_identity('abs:"two words" OR ti:a')
 assert query_identity('ti:a ANDNOT abs:b')!=query_identity('ti:a AND abs:b')
 assert query_identity('ti:"a b"')!=query_identity('ti:"ab"')
 assert query_identity('ti:a OR (abs:b AND cat:cs.LG)')!=query_identity('(ti:a OR abs:b) AND cat:cs.LG')
def test_migration_preserves_counts_aliases_and_scope_reuse():
 q='ti:a OR abs:b';q2='('+q+')'
 with Session.begin() as s:
  s.add(TrendSeries(id='preset-test',name='Existing topic',query=q))
  s.add(TrendSeries(id='explore-old',name='分子与材料 · 探索范围',query=q2))
  s.add(TrendCount(key=key(q2,'202501010000','202512312359'),count=18,source='fixture'))
 assert len(migrate_series())==1;assert migrate_series()==[]
 with Session.begin() as s:
  assert s.get(TrendCount,key(q,'202501010000','202512312359')).count==18
  assert ensure_scope(s,{'domain_id':'molecules','query':q2})=='preset-test'
 assert client.get('/api/trends/data',params={'ids':'explore-old','start':'2025','end':'2025'}).json()['series'][0]['points'][0]['count']==18
 assert client.post('/api/trends/series',headers=H,json={'name':'duplicate','query':q2}).json()['id']=='preset-test'
 r=client.post('/api/trends/series',headers=H,json={'name':'other','query':'ti:other'}).json()
 assert client.put('/api/trends/series/'+r['id'],headers=H,json={'name':'collision','query':q2}).status_code==409

def test_waiting_job_deduplication_and_snapshot_reuse():
 jid=enqueue('explore',{'query':'ti:a OR abs:b'})
 with Session.begin() as s:s.get(Job,jid).status='waiting'
 assert enqueue('explore',{'query':'(abs:b OR ti:a)'})==jid
 with patch('backend.history.search_page',return_value=([],0)) as remote:
  collect('ti:a','2025-01-01','2025-01-31')
  collect('(ti:a)','2025-01-01','2025-01-31')
  assert remote.call_count==1

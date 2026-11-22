"""Trend-series identity and lossless migration of automatically duplicated scopes."""
import calendar,hashlib
from datetime import date
from sqlalchemy import select
from .db import Session,TrendSeries,TrendCount,Setting,Domain
from .query_identity import query_identity

def find_series(s,query,exclude=None):
 identity=query_identity(query)
 return next((r for r in s.scalars(select(TrendSeries).order_by(TrendSeries.id)) if r.id!=exclude and query_identity(r.query)==identity),None)
def ensure_scope(s,scope):
 if s.bind.dialect.name=='sqlite':s.connection().exec_driver_sql('BEGIN IMMEDIATE')
 existing=find_series(s,scope['query'])
 if existing:return existing.id
 d=s.get(Domain,scope['domain_id']);identity=query_identity(scope['query'])
 suffix='全领域' if query_identity(d.query)==identity else '自定义检索 · '+scope['query'][:28]
 row=TrendSeries(id='explore-'+hashlib.sha256(identity.encode()).hexdigest()[:20],name=(d.name+' · '+suffix)[:80],query=scope['query'],color=d.color);s.add(row)
 return row.id

def aliases(s):
 r=s.get(Setting,'trend_series_aliases');return r.value if r else {}
def migrate_series():
 from .trends import key
 report=[]
 with Session.begin() as s:
  if s.bind.dialect.name=='sqlite':s.connection().exec_driver_sql('BEGIN IMMEDIATE')
  rows=list(s.scalars(select(TrendSeries)));groups={};mapping=aliases(s)
  counts={r.key:r for r in s.scalars(select(TrendCount))}
  periods=[]
  for year in range(1991,date.today().year+1):
   periods.append((f'{year}01010000',f'{year}12312359'))
   for month in range(1,13):periods.append((f'{year}{month:02}010000',f'{year}{month:02}{calendar.monthrange(year,month)[1]}2359'))
  for row in rows:groups.setdefault(query_identity(row.query),[]).append(row)
  domains=list(s.scalars(select(Domain)))
  for group in groups.values():
   group.sort(key=lambda r:(r.id.startswith('explore-'),not r.id.startswith('preset-'),r.id));keep=group[0]
   for old in group[1:]:
    for lo,hi in periods:
     src=counts.get(key(old.query,lo,hi));target=key(keep.query,lo,hi);dst=counts.get(target)
     if src and (not dst or src.fetched>dst.fetched):
      if dst:dst.count=src.count;dst.source=src.source;dst.fetched=src.fetched
      else:
       dst=TrendCount(key=target,count=src.count,source=src.source,fetched=src.fetched);s.add(dst);counts[target]=dst
    mapping[old.id]=keep.id;report.append({'merged':old.id,'into':keep.id});s.delete(old)
   if keep.id.startswith('explore-') and '探索范围' in keep.name:
    d=next((d for d in domains if query_identity(d.query)==query_identity(keep.query)),None)
    keep.name=(d.name+' · 全领域') if d else (keep.name.replace('探索范围','自定义检索')+' · '+keep.query[:28])[:80]
  for old,target in list(mapping.items()):
   seen={old}
   while target in mapping and target not in seen:seen.add(target);target=mapping[target]
   mapping[old]=target
  s.merge(Setting(key='trend_series_aliases',value=mapping))
 return report

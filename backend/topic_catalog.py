"""Shared direction vocabulary; classification and trend series share stable identity."""
import json,hashlib
from pathlib import Path
from sqlalchemy import select
from .db import Session,Domain,TrendSeries,Setting
from .trend_identity import find_series
CATALOG=json.loads(Path(__file__).with_suffix('.json').read_text('utf8'))

def sync_directions():
    with Session.begin() as s:
        s.connection().exec_driver_sql('BEGIN IMMEDIATE')
        saved=s.get(Setting,'trend_topic_identity');mapping=dict(saved.value) if saved else {}
        parent=s.get(Setting,'trend_parents');parents=dict(parent.value) if parent else {}
        created=0
        for d in s.scalars(select(Domain)):
            definitions={x['name']:{**x,'definition':x.get('definition') or x.get('description','')} for x in d.definitions}
            for item in CATALOG:
                if item['domain']!=d.name or item['name'] not in d.topics:continue
                name=item['name'];key=d.id+':'+name
                row=s.get(TrendSeries,mapping.get(key,''))
                if not row and item['preset']:row=s.get(TrendSeries,item['preset'])
                if not row:
                    row=next((r for r in s.scalars(select(TrendSeries)) if r.name==name and parents.get(r.id,d.id)==d.id),None)
                if not row:row=find_series(s,item['query'])
                if not row:
                    row=TrendSeries(id='topic-'+hashlib.sha256(key.encode()).hexdigest()[:20],name=name,query=item['query'],color=d.color);s.add(row);s.flush();created+=1
                mapping[key]=row.id;parents[row.id]=d.id
                definitions.setdefault(name,{'name':name,'definition':item['description']})
            d.definitions=list(definitions.values())
        s.merge(Setting(key='trend_topic_identity',value=mapping));s.merge(Setting(key='trend_parents',value=parents))
    return {'created':created,'directions':len(mapping)}

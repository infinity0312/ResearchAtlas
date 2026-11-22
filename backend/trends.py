import hashlib,calendar,re
from datetime import datetime,timezone,timedelta
from typing import Literal
from fastapi import APIRouter,HTTPException,Query
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select
from defusedxml import ElementTree as ET
import httpx
from .db import Session,TrendSeries,TrendCount,Job,now,serialize,Domain,Setting
from .services import enqueue
from .trend_identity import find_series,aliases,ensure_scope
from .query_identity import query_identity
from .sources import arxiv_wait,NS
router=APIRouter(prefix='/api/trends')
PRESETS=[('分子性质预测','(ti:"molecular property" OR abs:"molecular property prediction")'),('分子生成','(ti:"molecular generation" OR abs:"molecule generation" OR abs:"de novo drug design")'),('材料逆向设计','(abs:"inverse design" AND (abs:material OR abs:materials))'),('机器学习原子势','(abs:"machine learning potential" OR abs:"machine-learned interatomic" OR abs:"neural network potential")'),('蛋白质结构','(abs:"protein structure prediction" OR ti:AlphaFold)'),('蛋白质设计','(abs:"protein design" OR abs:"protein generation")'),('基因组学','(abs:genomics OR abs:genomic) AND (abs:learning OR abs:neural)'),('单细胞分析','(abs:"single-cell" OR abs:"single cell") AND (abs:learning OR abs:neural)'),('表示学习','(ti:"representation learning" OR abs:"representation learning")'),('生成模型','(ti:"generative model" OR abs:"diffusion model" OR abs:"flow matching")'),('优化与泛化','(ti:generalization OR ti:optimization) AND (abs:"machine learning" OR abs:"deep learning")'),('强化学习','(ti:"reinforcement learning" OR abs:"reinforcement learning")')]
def series_colors(s):
    ids=list(s.scalars(select(TrendSeries.id).order_by(TrendSeries.id)))
    return {id:f'hsl({(i*137.508+165)%360:.1f} 52% 43%)' for i,id in enumerate(ids)}

def seed_series():
    with Session.begin() as s:
        if s.scalar(select(TrendSeries.id).limit(1)):return
        for i,(name,query) in enumerate(PRESETS):s.add(TrendSeries(id=f'preset-{i}',name=name,query=query,color=['#327c72','#9671b2','#bd8742','#547eb1','#b06c7f','#7e964b'][i%6]))
class SeriesInput(BaseModel):
    name:str=Field(min_length=1,max_length=80)
    query:str=Field(min_length=3,max_length=2000)
    domain_id:str|None=None
    @field_validator('name','query')
    @classmethod
    def trim(cls,v):
        if not v.strip():raise ValueError('不能为空')
        if 'submittedDate:' in v:raise ValueError('日期由统计区间控制，请移除 submittedDate')
        return v.strip()
    @field_validator('query')
    @classmethod
    def executable_query(cls,v):
        from .history import branches
        branches(v)
        return v
def parent_domain(s,row):
    domains=list(s.scalars(select(Domain)))
    root=next((d for d in domains if query_identity(d.query)==query_identity(row.query)),None)
    if root:return root.id,True
    saved=s.get(Setting,'trend_parents');mapping=saved.value if saved else {}
    if row.id in mapping:return mapping[row.id],False
    if row.id.startswith('preset-'):
        try:
            n=int(row.id.split('-')[1]);return ('molecules' if n<4 else 'life' if n<8 else 'ml'),False
        except ValueError:pass
    match=next((d for d in domains if row.name.startswith(d.name+' · ') or row.name in d.topics),None)
    return (match.id if match else None),False

def set_parent(s,id,domain_id):
    if domain_id is None:return
    if not s.get(Domain,domain_id):raise HTTPException(404,'所属领域不存在')
    saved=s.get(Setting,'trend_parents');mapping=dict(saved.value) if saved else {};mapping[id]=domain_id
    s.merge(Setting(key='trend_parents',value=mapping))

@router.get('/series')
def series():
    from .topic_catalog import sync_directions
    sync_directions()
    with Session() as s:domains=list(s.scalars(select(Domain)))
    for d in domains:
        with Session.begin() as s:ensure_scope(s,{'domain_id':d.id,'query':d.query})
    with Session() as s:
        mapping=aliases(s);colors=series_colors(s);result=[]
        for x in s.scalars(select(TrendSeries).order_by(TrendSeries.name)):
            domain_id,is_root=parent_domain(s,x)
            result.append({**serialize(x),'color':colors[x.id],'domain_id':domain_id,'is_root':is_root,'aliases':[old for old,target in mapping.items() if target==x.id]})
        return result
@router.post('/series')
def create(data:SeriesInput):
    with Session.begin() as s:
        if s.bind.dialect.name=='sqlite':s.connection().exec_driver_sql('BEGIN IMMEDIATE')
        existing=find_series(s,data.query)
        if existing:
            set_parent(s,existing.id,data.domain_id);return serialize(existing)
        row=TrendSeries(**data.model_dump(exclude={'domain_id'}));s.add(row);s.flush();set_parent(s,row.id,data.domain_id);return serialize(row)
@router.put('/series/{id}')
def edit(id:str,data:SeriesInput):
    with Session.begin() as s:
        if s.bind.dialect.name=='sqlite':s.connection().exec_driver_sql('BEGIN IMMEDIATE')
        row=s.get(TrendSeries,id)
        if not row:raise HTTPException(404,'方向不存在')
        existing=find_series(s,data.query,exclude=id)
        if existing:raise HTTPException(409,'此检索范围已存在：'+existing.name)
        row.name=data.name;row.query=data.query;set_parent(s,row.id,data.domain_id);return serialize(row)

def buckets(start,end,interval):
    pattern=r'\d{4}' if interval=='year' else r'\d{4}-\d{2}'
    if not re.fullmatch(pattern,start) or not re.fullmatch(pattern,end):raise ValueError('年度格式 YYYY，月度格式 YYYY-MM')
    try:
        a=datetime.strptime(start,'%Y' if interval=='year' else '%Y-%m');b=datetime.strptime(end,'%Y' if interval=='year' else '%Y-%m')
    except ValueError:raise ValueError('统计日期无效')
    if a>b or a.year<1991 or b>datetime.now():raise ValueError('区间须在 1991 年至当前月份之间')
    out=[]
    while a<=b:
        if len(out)>=60:raise ValueError('一次最多 60 个时间点')
        stop=datetime(a.year,12,31,23,59) if interval=='year' else datetime(a.year,a.month,calendar.monthrange(a.year,a.month)[1],23,59)
        out.append((a.strftime('%Y' if interval=='year' else '%Y-%m'),a.strftime('%Y%m%d%H%M'),stop.strftime('%Y%m%d%H%M')))
        a=datetime(a.year+1,1,1) if interval=='year' or a.month==12 else datetime(a.year,a.month+1,1)
    return out

def key(query,lo,hi):return hashlib.sha256((query+'|'+lo+'|'+hi).encode()).hexdigest()
def count_remote(query):
    arxiv_wait()
    try:
        r=httpx.get('https://export.arxiv.org/api/query',params={'search_query':query,'start':0,'max_results':1},timeout=35,headers={'User-Agent':'ResearchAtlas/0.2 personal research trends'})
        r.raise_for_status();root=ET.fromstring(r.text)
        if any('/api/errors' in (e.findtext('a:id','',NS)) for e in root.findall('a:entry',NS)):raise ValueError('检索表达式被 arXiv 拒绝')
        raw=root.findtext('o:totalResults',None,NS)
        if raw is None or not raw.isdigit():raise ValueError('arXiv 未返回有效总数')
        return int(raw)
    except httpx.HTTPStatusError as e:raise RuntimeError(f'arXiv 宏观统计接口返回 HTTP {e.response.status_code}；已获取的数据保留，未获取的时间点为空，可稍后重试') from None
    except httpx.RequestError:raise RuntimeError('arXiv 宏观统计接口暂时无法连接，请稍后重试') from None

class RequestInput(BaseModel):
    ids:list[str]=Field(min_length=1,max_length=6)
    start:str
    end:str
    interval:Literal['year','month']='year'
    quality:bool=False
    full_index:bool=False

def resolve(ids,start,end,interval):
    try:bs=buckets(start,end,interval)
    except ValueError as e:raise HTTPException(422,str(e))
    with Session() as s:
        mapping=aliases(s);ids=list(dict.fromkeys(mapping.get(id,id) for id in ids))
        rows=list(s.scalars(select(TrendSeries).where(TrendSeries.id.in_(ids))))
        if len(rows)!=len(set(ids)):raise HTTPException(404,'方向不存在')
    return rows,bs
@router.post('/refresh',status_code=202)
def refresh(data:RequestInput):
    rows,bs=resolve(data.ids,data.start,data.end,data.interval)
    payload={**data.model_dump(),'series':[serialize(x) for x in rows]}
    return {'job_id':enqueue('trends',payload)}
@router.get('/data')
def data(ids:list[str]=Query(default=[]),start:str='2020',end:str='2025',interval:Literal['year','month']='year'):
    if len(ids)>6:raise HTTPException(422,'最多比较 6 个方向')
    rows,bs=resolve(ids,start,end,interval)
    result=[]
    with Session() as s:
        colors=series_colors(s)
        for row in rows:
            points=[]
            for label,lo,hi in bs:
                cached=s.get(TrendCount,key(row.query,lo,hi));points.append({'period':label,'count':cached.count if cached else None,'fetched':cached.fetched if cached else None,'source':cached.source if cached else None,'partial':hi>datetime.now(timezone.utc).strftime('%Y%m%d%H%M')})
            complete=[p for p in points if not p['partial']]
            growth=None
            if len(complete)>1 and complete[-1]['count'] is not None and complete[-2]['count'] not in (None,0):growth=round((complete[-1]['count']/complete[-2]['count']-1)*100,1)
            from .trend_signals import insight
            result.append({**serialize(row),'color':colors[row.id],'points':points,'growth':growth,'insight':insight(row.query,bs,points)})
        return {'series':result,'source':'arXiv 官方索引 · 全站检索' ,'date_basis':'首次提交时间 UTC','overlap':True}

def run_trends(job,progress):
    bs=buckets(job.payload['start'],job.payload['end'],job.payload['interval']);rows=job.payload['series'];done=0;total=len(bs)*len(rows)
    if job.payload.get('full_index'):
        from .history import collect
        from collections import Counter
        today=datetime.now(timezone.utc).date()
        for row in rows:
            start=datetime.strptime(bs[0][1][:8],'%Y%m%d').date().isoformat()
            end=min(datetime.strptime(bs[-1][2][:8],'%Y%m%d').date(),today).isoformat()
            papers,snapshot=collect(row['query'],start,end,lambda message:progress(job.id,5,message))
            yearly=Counter(p['published'][:4] for p in papers);monthly=Counter(p['published'][:7] for p in papers)
            # One complete population feeds both resolutions, including real zero-count periods.
            with Session.begin() as s:
                for label,lo,hi in bs:
                    s.merge(TrendCount(key=key(row['query'],lo,hi),count=yearly[label] if job.payload['interval']=='year' else monthly[label],fetched=now(),source='arxiv-official-search'))
                if job.payload['interval']=='year':
                    for year in range(int(job.payload['start']),int(job.payload['end'])+1):
                        endmonth=today.month if year==today.year else 12
                        for label,lo,hi in buckets(f'{year}-01',f'{year}-{endmonth:02}','month'):
                            s.merge(TrendCount(key=key(row['query'],lo,hi),count=monthly[label],fetched=now(),source='arxiv-official-search'))
            progress(job.id,95,f"完整索引已保存：{row['name']} · {len(papers)} 篇，年/月统计同步完成")
        if not job.payload.get('quality'):return {'message':'完整历史索引与年/月统计已补齐','complete':True}
    for row in rows:
        for label,lo,hi in bs:
            cachekey=key(row['query'],lo,hi)
            with Session() as s:cached=s.get(TrendCount,cachekey)
            if not cached or datetime.fromisoformat(cached.fetched)<datetime.now(timezone.utc)-timedelta(days=7):
                source='arxiv-api'
                try:count=count_remote(f"({row['query']}) AND submittedDate:[{lo} TO {hi}]")
                except RuntimeError:
                    from .history import collect
                    start=datetime.strptime(lo[:8],'%Y%m%d').date().isoformat();end=min(datetime.strptime(hi[:8],'%Y%m%d').date(),datetime.now(timezone.utc).date()).isoformat()
                    papers,_=collect(row['query'],start,end,lambda m:progress(job.id,int(done/total*100),m));count=len(papers);source='arxiv-official-search'
                with Session.begin() as s:s.merge(TrendCount(key=cachekey,count=count,fetched=now(),source=source))
            done+=1;progress(job.id,int(done/total*100),f"宏观趋势：{row['name']} · {label}（{done}/{total}）")
    if job.payload.get('quality'):
        from .trend_reviews import packet
        from .macro_coauthor import prepare
        complete=[b for b in bs if b[2]<datetime.now(timezone.utc).strftime('%Y%m%d%H%M')][-3:]
        for row in rows:
            for label,lo,hi in complete:
                progress(job.id,95,f"分析创新信号：{row['name']} · {label}")
                # Coauthor review uses complete calendar years; counts retain any selected granularity.
                year=int(lo[:4])
                if year>=datetime.now(timezone.utc).year:continue
                from .history import collect
                collect(row['query'],f'{year}-01-01',f'{year}-12-31',lambda m:progress(job.id,95,m))
                with Session() as s:source=packet(s,row['id'],year)
                if source['query']!=row['query']:raise RuntimeError('检索口径已改变，请重新提交趋势任务')
                prepare(source)
    return {'message':f'已完成 {total} 个时间点统计'+('；年度创新信号已交接协作队列，待生成与 GPT 复核' if job.payload.get('quality') else '')}

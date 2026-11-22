"""Official arXiv historical search, complete pagination and resumable metadata cache."""
import re,json,hashlib,time
from datetime import datetime,timedelta,timezone,date
from sqlalchemy import select
import httpx
from bs4 import BeautifulSoup
from .db import Session,CatalogPaper,SearchSnapshot,SearchPage,now
from .sources import arxiv_wait
VERSION='official-search-v1'
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def branches(query):
    tokens=[];pos=0
    pattern=r'\s*(ANDNOT\b|AND\b|OR\b|\(|\)|(?:cat|all|ti|abs|au):(?:"[^"]+"|[^\s()]+))'
    while pos<len(query):
        if not query[pos:].strip():break
        m=re.match(pattern,query[pos:])
        if not m:raise ValueError('历史检索支持 cat/all/ti/abs/au、AND/OR/ANDNOT 与括号')
        tokens.append(m.group(1));pos+=m.end()
    i=0
    def atom():
        nonlocal i
        if i>=len(tokens):raise ValueError('检索式不完整')
        t=tokens[i];i+=1
        if t=='(':
            n=disj()
            if i>=len(tokens) or tokens[i]!=')':raise ValueError('检索括号不匹配')
            i+=1;return n
        if ':' not in t:raise ValueError('检索项无效')
        return ('atom',t)
    def conj():
        nonlocal i
        n=atom()
        while i<len(tokens) and tokens[i] in ('AND','ANDNOT'):
            op=tokens[i];i+=1;n=(op,n,atom())
        return n
    def disj():
        nonlocal i
        n=conj()
        while i<len(tokens) and tokens[i]=='OR':i+=1;n=('OR',n,conj())
        return n
    tree=disj()
    if i!=len(tokens):raise ValueError('检索式存在多余项')
    def dnf(n,neg=False):
        if n[0]=='atom':return [[(n[1],neg)]]
        op=n[0];left=dnf(n[1],neg);right=dnf(n[2],not neg if op=='ANDNOT' else neg)
        union=(op=='OR')!=neg
        result=left+right if union else [a+b for a in left for b in right]
        if len(result)>64:raise ValueError('检索式展开超过 64 个分支，请缩小范围')
        return result
    return dnf(tree)

def parse_search(html):
    soup=BeautifulSoup(html,'html.parser');heading=soup.select_one('h1.title')
    text=heading.get_text(' ',strip=True) if heading else ''
    m=re.search(r'of\s+([\d,]+)\s+results?',text,re.I)
    if m:total=int(m.group(1).replace(',',''))
    elif 'no results' in soup.get_text(' ',strip=True).lower():return [],0
    else:raise ValueError('arXiv 检索页格式变化，无法确认总数，未标记完成')
    papers=[]
    for item in soup.select('li.arxiv-result'):
        anchor=item.select_one('.list-title a');title=item.select_one('p.title');abstract=item.select_one('.abstract-full')
        if not anchor or not title or not abstract:raise ValueError('检索记录缺少标题或完整摘要')
        pid=re.sub(r'v\d+$','',anchor.get_text(strip=True).removeprefix('arXiv:'));v=re.search(r'v(\d+)-abstract-full',abstract.get('id',''));version=int(v.group(1)) if v else 1
        for a in abstract.select('a'):a.decompose()
        date_line=next((p.get_text(' ',strip=True) for p in item.select('p.is-size-7') if 'Submitted' in p.get_text()),'')
        dates=re.findall(r'(\d{1,2} [A-Za-z]+, \d{4})',date_line)
        if not dates:raise ValueError('检索记录缺少提交日期')
        updated=datetime.strptime(dates[0],'%d %B, %Y').replace(tzinfo=timezone.utc).isoformat()
        first=datetime.strptime(dates[1] if len(dates)>1 else dates[0],'%d %B, %Y').replace(tzinfo=timezone.utc).isoformat()
        papers.append(dict(id=pid,version=version,title=title.get_text(' ',strip=True),abstract=abstract.get_text(' ',strip=True),authors=[a.get_text(' ',strip=True) for a in item.select('.authors a')],categories=[t.get_text(strip=True) for t in item.select('.tags .tag')],published=first,updated=updated,date_basis='submitted'))
    if total and not papers:raise ValueError('检索页缺少论文记录，未标记完成')
    return papers,total

def fresh(timestamp,hours=168):return datetime.fromisoformat(timestamp)>datetime.now(timezone.utc)-timedelta(hours=hours)
def search_page(branch,start,end,offset=0):
    params={'advanced':'1','classification-include_cross_list':'include','date-filter_by':'date_range','date-from_date':start,'date-to_date':end,'date-date_type':'submitted_date_first','abstracts':'show','size':'200','order':'-announced_date_first','start':offset}
    fields={'ti':'title','abs':'abstract','all':'all','au':'author','cat':'cross_list_category'}
    for i,(token,negative) in enumerate(branch):
        field,value=token.split(':',1)
        params.update({f'terms-{i}-operator':'NOT' if negative else 'AND',f'terms-{i}-term':value,f'terms-{i}-field':fields[field]})
    k=digest([VERSION,params])
    with Session() as s:cached=s.get(SearchPage,k)
    if cached and fresh(cached.fetched,6 if end>=date.today().isoformat() else 168):return cached.result['papers'],cached.result['total']
    for attempt in range(3):
        arxiv_wait()
        try:
            r=httpx.get('https://arxiv.org/search/advanced',params=params,timeout=60,follow_redirects=True,headers={'User-Agent':'ResearchAtlas/0.3 personal literature research'})
            r.raise_for_status();papers,total=parse_search(r.text);break
        except (httpx.RequestError,httpx.HTTPStatusError) as e:
            if attempt==2:raise RuntimeError('arXiv 官方历史检索暂时不可用，已完成页保留；可重试续传') from e
            time.sleep(3*(attempt+1))
    with Session.begin() as s:s.merge(SearchPage(key=k,result={'papers':papers,'total':total},fetched=now()))
    return papers,total

def collect(query,start,end,progress=lambda message:None,stop=lambda:False):
    from .query_identity import query_identity
    k=digest([VERSION,query_identity(query),start,end]);today=date.today().isoformat();ttl=6 if end>=today else 168
    with Session() as s:
        cached=s.get(SearchSnapshot,k)
        if cached and cached.complete and fresh(cached.fetched,ttl):
            result=[s.get(CatalogPaper,pid).metadata_json for pid in cached.paper_ids]
            progress(f'复用已完成检索：{len(result)} 篇');return result,k
    with Session() as s:
        covering=s.scalars(select(SearchSnapshot).where(SearchSnapshot.complete==True,SearchSnapshot.start<=start,SearchSnapshot.end>=end).order_by(SearchSnapshot.fetched.desc()))
        for snapshot in covering:
            if query_identity(snapshot.query)!=query_identity(query):continue
            if fresh(snapshot.fetched,ttl):
                rows=[s.get(CatalogPaper,pid).metadata_json for pid in snapshot.paper_ids]
                rows=[p for p in rows if start<=p['published'][:10]<=end]
                progress(f'复用覆盖该区间的完整索引：{len(rows)} 篇');return rows,snapshot.key
    parts=branches(query);found={}
    def gather(branch,lo,hi):
        if stop():raise ValueError('探索已取消；已完成数据保留')
        # Use next-day boundary, then enforce an inclusive first-submission date locally.
        until=(date.fromisoformat(hi)+timedelta(days=1)).isoformat()
        first,total=search_page(branch,lo,until)
        if total>9500:
            a=date.fromisoformat(lo);b=date.fromisoformat(hi)
            if a==b:raise ValueError('单日匹配超过检索分页上限，请缩小检索式；未使用截断数据统计')
            mid=a+(b-a)//2;gather(branch,lo,mid.isoformat());gather(branch,(mid+timedelta(days=1)).isoformat(),hi);return
        rows=first;seen=set();offset=0
        while True:
            if stop():raise ValueError('探索已取消；已完成数据保留')
            before=len(seen);seen.update(p['id'] for p in rows)
            if total and len(seen)==before:raise ValueError('检索分页重复，未确认完整覆盖')
            for p in rows:
                if lo<=p['published'][:10]<=hi:found[p['id']]=p
            progress(f'历史检索已收集 {len(found)} 篇元数据（分支 {min(offset+len(rows),total)}/{total}）')
            offset+=len(rows)
            if offset>=total:
                if len(seen)!=total:raise ValueError('分页记录去重后与总数不符，未确认完整覆盖')
                break
            rows,current_total=search_page(branch,lo,until,offset)
            if current_total!=total:raise ValueError('检索索引在分页期间变化，请重试以确认覆盖')
    for branch in parts:gather(branch,start,end)
    with Session.begin() as s:
        for p in found.values():
            old=s.get(CatalogPaper,p['id'])
            if not old or old.metadata_json.get('version',0)<=p['version']:s.merge(CatalogPaper(id=p['id'],metadata_json=p,fetched=now()))
        s.merge(SearchSnapshot(key=k,query=query,start=start,end=end,paper_ids=sorted(found),source='arxiv-official-search',complete=True,fetched=now()))
    return list(found.values()),k

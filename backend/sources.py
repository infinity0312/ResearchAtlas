import re, time, fnmatch
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
import httpx
from defusedxml import ElementTree as ET
from .db import Session, Setting

ARXIV_ID = re.compile(r'^(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v(\d+))?$')
NS = {'a':'http://www.w3.org/2005/Atom','o':'http://a9.com/-/spec/opensearch/1.1/'}

def parse_atom(xml: str):
    root = ET.fromstring(xml)
    total = int(root.findtext('o:totalResults', default='0', namespaces=NS))
    papers=[]
    for entry in root.findall('a:entry', NS):
        raw = entry.findtext('a:id', default='', namespaces=NS).split('/abs/')[-1]
        match=ARXIV_ID.fullmatch(raw)
        if not match: continue
        version=int(match.group(1) or 1)
        pid=re.sub(r'v\d+$','',raw)
        def t(tag): return ' '.join(entry.findtext('a:'+tag, default='', namespaces=NS).split())
        papers.append(dict(id=pid, version=version, title=t('title'), abstract=t('summary'), published=t('published'), updated=t('updated'), authors=[a.findtext('a:name', namespaces=NS) for a in entry.findall('a:author',NS)], categories=[a.attrib['term'] for a in entry.findall('a:category',NS)]))
    return papers,total

def arxiv_wait():
    # Only the single worker fetches sources; persist timestamp across restarts.
    with Session.begin() as s:
        state=s.get(Setting,'arxiv_clock')
        previous=state.value.get('time',0) if state else 0
        delay=max(0,3.2-(time.time()-previous))
        if delay: time.sleep(delay)
        if state: state.value={'time':time.time()}
        else: s.add(Setting(key='arxiv_clock',value={'time':time.time()}))

class ArxivSource:
    def fetch(self, query, start=0, size=100):
        for attempt in range(3):
            arxiv_wait()
            try:
                response=httpx.get('https://export.arxiv.org/api/query',params={'search_query':query,'start':start,'max_results':size,'sortBy':'lastUpdatedDate','sortOrder':'descending'},timeout=45,headers={'User-Agent':'ResearchAtlas/0.1 personal literature manager'})
                if response.status_code==406: raise ValueError('arXiv API 返回 406，历史回填不可用')
                response.raise_for_status()
                return parse_atom(response.text)
            except (httpx.TimeoutException,httpx.HTTPStatusError,httpx.ConnectError):
                if attempt==2: raise RuntimeError('arXiv 暂时无法访问；请稍后重试，已有文献不受影响') from None
                time.sleep(3*(attempt+1))

def matches_query(query,item):
    pattern=r'\s*(ANDNOT\b|AND\b|OR\b|\(|\)|(?:cat|all|ti|abs):(?:"[^"]+"|[^\s()]+))'
    tokens=[]; pos=0
    while pos<len(query):
        if not query[pos:].strip(): break
        m=re.match(pattern,query[pos:])
        if not m: raise ValueError('RSS 降级暂仅支持 cat/all/ti/abs、AND/OR/ANDNOT 与括号')
        tokens.append(m.group(1)); pos+=m.end()
    idx=0
    def atom():
        nonlocal idx
        if idx>=len(tokens): raise ValueError('查询语法不完整')
        token=tokens[idx];idx+=1
        if token=='(':
            value=disjunction()
            if idx>=len(tokens) or tokens[idx]!=')': raise ValueError('查询括号不匹配')
            idx+=1;return value
        if ':' not in token: raise ValueError('查询项无效')
        field,value=token.split(':',1);value=value.strip('"').casefold()
        if field=='cat': return any(fnmatch.fnmatchcase(c.casefold(),value) for c in item['categories'])
        target=item['title'] if field=='ti' else item['abstract'] if field=='abs' else item['title']+' '+item['abstract']
        return value in target.casefold()
    def conjunction():
        nonlocal idx
        v=atom()
        while idx<len(tokens) and tokens[idx] in ('AND','ANDNOT'):
            op=tokens[idx];idx+=1;rhs=atom();v=v and (not rhs if op=='ANDNOT' else rhs)
        return v
    def disjunction():
        nonlocal idx
        v=conjunction()
        while idx<len(tokens) and tokens[idx]=='OR':
            idx+=1;rhs=conjunction();v=v or rhs
        return v
    value=disjunction()
    if idx!=len(tokens): raise ValueError('查询语法无效')
    return value

def parse_rss(xml):
    root=ET.fromstring(xml);items=[]
    for entry in root.findall('channel/item'):
        raw=entry.findtext('guid',default='').split('oai:arXiv.org:')[-1]
        match=ARXIV_ID.fullmatch(raw)
        if not match: continue
        desc=entry.findtext('description',default='')
        date=parsedate_to_datetime(entry.findtext('pubDate')).astimezone(timezone.utc).isoformat()
        items.append({'id':re.sub(r'v\d+$','',raw),'version':int(match.group(1) or 1),'title':entry.findtext('title',default=''),'abstract':desc.split('Abstract:',1)[-1].strip(),'authors':[n.strip() for n in entry.findtext('{http://purl.org/dc/elements/1.1/}creator',default='').split(',')],'categories':[c.text for c in entry.findall('category')],'published':date,'updated':date,'date_basis':'announcement'})
    return items

class ArxivRssSource:
    def fetch_daily(self,query):
        categories=list(dict.fromkeys(re.findall(r'cat:([a-zA-Z0-9.-]+)',query)))
        if not categories: raise ValueError('RSS 降级需要明确的 arXiv 分类，请编辑订阅规则')
        found={}
        for category in categories:
            arxiv_wait()
            r=httpx.get('https://rss.arxiv.org/rss/'+category,timeout=45)
            r.raise_for_status()
            for item in parse_rss(r.text):
                if matches_query(query,item): found[item['id']]=item
        return list(found.values())

def download_pdf(paper_id, version, target):
    if not ARXIV_ID.fullmatch(paper_id): raise ValueError('无效 arXiv ID')
    arxiv_wait()
    url=f'https://arxiv.org/pdf/{paper_id}v{version}'
    partial=target.with_suffix(target.suffix+'.part')
    try:
        with httpx.Client(timeout=60, follow_redirects=False) as client:
            with client.stream('GET',url) as response:
                response.raise_for_status()
                count=0
                with partial.open('wb') as f:
                    for chunk in response.iter_bytes():
                        count+=len(chunk)
                        if count>80*1024*1024: raise ValueError('全文超过 80MB 下载上限，请分卷处理')
                        f.write(chunk)
        with partial.open('rb') as f:
            if not f.read(1024).lstrip().startswith(b'%PDF'): raise ValueError('获取的内容不是 PDF')
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)

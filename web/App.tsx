import {useEditionSwatch} from './ui/industrial/colors';
import IndustrialHeading from './ui/industrial/IndustrialHeading';
import {useAppearance} from './ui/Appearance';
import PageBoundary from './ui/PageBoundary';
import PaperRow from './PaperLibraryRow';
import MapSectionNav from './MapSectionNav';
import {WorkspaceSidebar,WorkspaceHeader} from './app/WorkspaceChrome';
import SettingsForm from './app/ConnectionSettings';
import {lazy,Suspense,useEffect,useLayoutEffect,useState,useRef,type FormEvent} from 'react';
import {useQuery,useInfiniteQuery,useQueryClient} from '@tanstack/react-query';
import {Trash2,FolderOpen,Menu,Activity,TrendingUp,ArrowDownToLine,ArrowRight,ArrowUpRight,BookOpen,NotebookPen,Bookmark,Check,CheckCircle2,ChevronLeft,ChevronRight,Circle,Clock3,Compass,FileText,FlaskConical,Layers3,LayoutDashboard,LoaderCircle,Plus,RefreshCw,Search,Settings2,SlidersHorizontal,Sparkles,Upload,X,ExternalLink,TriangleAlert,KeyRound,Network} from 'lucide-react';
import {api,params,date,type Domain,type Paper,type Detail,type Job,type Overview,type Survey,type Claim} from './api';
import Modal from './Modal';
import AppearanceSettings from './ui/AppearanceSettings';
import {useWorkspaceRoute,pageLabels as labels,type Page} from './app/useWorkspaceRoute';
import type {ProjectFocus,TrendFocus} from './product/projectNavigation';
const Projects=lazy(()=>import('./product/Projects'));
const WorkspacePanel=lazy(()=>import('./WorkspacePanel'));
import PaperImport from './PaperImport';
import './job-status.css';
import {useScrollActivity} from './useScrollActivity';
import DomainMultiSelect from './DomainMultiSelect';
import MathText from './MathText';
import AnalysisQuality from './AnalysisQuality';
import RelatedPapers from './RelatedPapers';
import {PaperTags} from './Tags';
import ExplorationStatus,{ExplorationDialog} from './Exploration';
const MethodMatrix=lazy(()=>import('./MethodMatrix'));
const Trends=lazy(()=>import('./Trends'));
const RelationGraph=lazy(()=>import('./RelationGraph'));
const Chart=lazy(()=>import('./Chart'));
const PaperDetail=lazy(()=>import('./PaperDetail'));
const Notes=lazy(()=>import('./Notes'));
const JobsPage=lazy(()=>import('./app/JobsPage'));
const ModelBudgetSettings=lazy(()=>import('./app/ModelBudgetSettings'));
const Hierarchy=lazy(()=>import('./Hierarchy'));


function Empty({icon:Icon=Compass,title,description,action}:{icon?:typeof Compass;title:string;description:string;action?:React.ReactNode}){return <div className="empty"><div className="empty-icon"><Icon size={27}/></div><h3>{title}</h3><p>{description}</p>{action}</div>}
function Loading(){
 const {appearance}=useAppearance();
 if(appearance.edition==='industrial')return <div className="atlas-loading" role="status">
  <span>正在加载</span>
  <div aria-hidden="true"><i className="ef-skeleton line"/><i className="ef-skeleton line"/><i className="ef-skeleton line"/></div>
 </div>;
 return <div className="loading"><LoaderCircle size={20} className="spin"/> 正在加载</div>;
}

export default function App(){
 const swatch=useEditionSwatch();
 useScrollActivity();
 const qc=useQueryClient();
 const [compact,setCompact]=useState(()=>matchMedia('(max-width:900px)').matches),[navOpen,setNavOpen]=useState(false);
 const navRef=useRef<HTMLElement>(null),navToggle=useRef<HTMLButtonElement>(null);
 useEffect(()=>{const media=matchMedia('(max-width:900px)');const change=()=>{setCompact(media.matches);setNavOpen(false)};media.addEventListener('change',change);return()=>media.removeEventListener('change',change)},[]);
 useEffect(()=>{if(!compact||!navOpen)return;const old=document.body.style.overflow;document.body.style.overflow='hidden';navRef.current?.querySelector<HTMLButtonElement>('.mobile-nav-close')?.focus();const key=(e:KeyboardEvent)=>{if(e.key==='Escape')setNavOpen(false)};window.addEventListener('keydown',key);return()=>{document.body.style.overflow=old;window.removeEventListener('keydown',key);navToggle.current?.focus()}},[compact,navOpen]);
 const {page,setPage,domain,setDomain,mapDomains,setMapDomains,days,setDays,projectTarget,setProjectTarget,trendTarget,setTrendTarget}=useWorkspaceRoute();
 const [mapAllHistory,setMapAllHistory]=useState(true);
 const [search,setSearch]=useState(''),[debounced,setDebounced]=useState('');
 const [facet,setFacet]=useState<{category?:string;topic?:string;method?:string}>({});
 const [exploring,setExploring]=useState(false),[importing,setImporting]=useState(false);
 const [toast,setToast]=useState(''),[busy,setBusy]=useState(false);
 const [paperId,setPaperId]=useState<string|null>(null),[editDomain,setEditDomain]=useState<Domain|'new'|null>(null);
 const searchRef=useRef<HTMLInputElement>(null);
 const domains=useQuery({queryKey:['domains'],queryFn:()=>api<Domain[]>('/domains')});
 const jobs=useQuery({queryKey:['jobs'],queryFn:()=>api<Job[]>('/jobs'),refetchInterval:5000});
 const health=useQuery({queryKey:['health'],queryFn:()=>api<{worker:boolean}>('/health'),refetchInterval:15000});
 const settings=useQuery({queryKey:['settings'],queryFn:()=>api<{has_key:boolean;model:string;daily_limit:number;auto_analyze:boolean}>('/settings')});
 const running=(jobs.data||[]).filter(j=>['running','queued'].includes(j.status));
 const active=domains.data?.find(d=>d.id===domain);
 const overview=useQuery({queryKey:['overview',domain,days],queryFn:()=>api<Overview>('/overview?'+params({domain_id:domain,days})),enabled:page==='overview'});
 const latest=useQuery({queryKey:['papers','latest',domain,days],queryFn:()=>api<{items:Paper[];total:number;pages:number}>('/papers?'+params({domain_id:domain,days,size:4})),enabled:page==='overview'});
 const [searchSort,setSearchSort]=useState<'research'|'recent'>('research');
 const feed=useInfiniteQuery({queryKey:['papers','feed',domain,days,debounced,page==='saved',facet,searchSort],initialPageParam:'',queryFn:({pageParam,signal})=>api<{items:Paper[];total:number;next_cursor:string|null}>('/papers?'+params({domain_id:domain,days:page==='saved'?0:days,q:debounced,sort:searchSort,saved:page==='saved',size:20,feed:true,cursor:pageParam,...facet}),{signal}),getNextPageParam:last=>last.next_cursor||undefined,enabled:page==='papers'||page==='saved'});
 const list=page==='overview'?latest:{...feed,data:feed.data?{items:[...new Map(feed.data.pages.flatMap(p=>p.items).map(p=>[p.id,p])).values()],total:feed.data.pages[0].total}:undefined};
 const sentinel=useRef<HTMLDivElement>(null);
 useEffect(()=>{const el=sentinel.current;if(!el||!feed.hasNextPage||feed.isFetching||feed.isError)return;const observer=new IntersectionObserver(entries=>{if(entries[0].isIntersecting)void feed.fetchNextPage()},{rootMargin:'400px'});observer.observe(el);return()=>observer.disconnect()},[page,feed.hasNextPage,feed.isFetching,feed.isError,feed.fetchNextPage]);

 const surveys=useQuery({queryKey:['surveys',domain],queryFn:()=>api<Survey[]>('/surveys?'+params({domain_id:domain})),enabled:page==='surveys'});
 const jobFingerprint=(jobs.data||[]).map(j=>j.id+j.status).join();
 useEffect(()=>{qc.invalidateQueries({queryKey:['papers']});qc.invalidateQueries({queryKey:['overview']});qc.invalidateQueries({queryKey:['surveys']});qc.invalidateQueries({queryKey:['domains']});qc.invalidateQueries({queryKey:['detail']});qc.invalidateQueries({queryKey:['tags']});qc.invalidateQueries({queryKey:['graph']});qc.invalidateQueries({queryKey:['paper-tags']})},[jobFingerprint,qc]);
 useEffect(()=>{const t=setTimeout(()=>setDebounced(search),250);return()=>clearTimeout(t)},[search]);


 useEffect(()=>{if(!toast)return;const t=setTimeout(()=>setToast(''),5000);return()=>clearTimeout(t)},[toast]);
 useEffect(()=>{const fn=(e:KeyboardEvent)=>{if((e.ctrlKey||e.metaKey)&&e.key==='k'){e.preventDefault();setPage('papers');setTimeout(()=>searchRef.current?.focus(),50)}};window.addEventListener('keydown',fn);return()=>window.removeEventListener('keydown',fn)},[]);
 useLayoutEffect(()=>{window.scrollTo({top:0,left:0,behavior:'instant'})},[page]);
 function navigate(next:Page){setNavOpen(false);if(!days&&!['papers','saved'].includes(next))setDays(30);setPage(next);setFacet({});setSearch('')}
 function openProject(target:ProjectFocus|null){setPaperId(null);setProjectTarget(target);setPage('projects');setNavOpen(false)}
 function openTrend(target:TrendFocus){setPaperId(null);setTrendTarget(target);setPage('trends');setNavOpen(false)}
 async function act(fn:()=>Promise<unknown>,success:string){setBusy(true);try{await fn();setToast(success);qc.invalidateQueries()}catch(e){setToast((e as Error).message)}finally{setBusy(false)}}
 const bookmark=(p:Paper)=>act(()=>api('/paper/state?id='+encodeURIComponent(p.id),{method:'PATCH',body:JSON.stringify({saved:!p.saved})}),p.saved?'已取消收藏':'已加入收藏');
 const drill=(name:string,isTopic=false,method?:string)=>{setFacet(isTopic?{topic:name,method}:{category:name});setPage('papers')};
 const data=overview.data;
 const timeline=data?.announcements ? data.daily.map(d=>({name:d.date.slice(5).replace('-','/'),value:d.count})) : Array.from({length:days},(_,i)=>{const d=new Date();d.setUTCDate(d.getUTCDate()-days+1+i);const key=d.toISOString().slice(0,10);return {name:key.slice(5).replace('-','/'),value:data?.daily.find(x=>x.date===key)?.count||0}});
 const error=domains.error||(page==='overview'&&overview.error)||(['papers','saved','overview'].includes(page)&&list.error);

 return <div data-page={page} className={"app-shell "+(['projects','papers','saved','map','trends'].includes(page)?'atlas-workspace ':'')+(navOpen?"nav-open":"")}>
  {compact&&navOpen&&<button className="nav-backdrop" aria-label="收起导航" onClick={()=>setNavOpen(false)}/>}
  <WorkspaceSidebar navRef={navRef} compact={compact} navOpen={navOpen} setNavOpen={setNavOpen} page={page} domain={domain} domains={domains.data||[]} navigate={navigate} onDomain={id=>{navigate('papers');setDomain(id);setMapDomains([id]);setDays(0)}} onAddDomain={()=>setEditDomain('new')} running={running.length} worker={!!health.data?.worker} onOpenData={()=>act(()=>api('/workspace/open',{method:'POST'}),'已打开本地数据文件夹')}/>

  <div className="main-shell" inert={compact&&navOpen}><WorkspaceHeader navToggle={navToggle} navOpen={navOpen} setNavOpen={setNavOpen} page={page} onSearch={()=>{navigate('papers');setTimeout(()=>searchRef.current?.focus(),50)}}/>
   <PageBoundary resetKey={page}><main className="page-transition">
    <div className="page-heading"><IndustrialHeading key={page}/><div><div className="eyebrow">RESEARCH ATLAS / {page==='overview'?'OVERVIEW':page.toUpperCase()}</div><h1>{labels[page]}<span className="heading-dot">.</span></h1><p>{({projects:'围绕决策问题组织证据，形成可复核、可追溯的研发交付。',overview:'从新的发现出发，看见研究方向的变化。',papers:'找到值得阅读的论文，保留每一条发现的依据。',map:'从领域到方法，探索论文之间的联系。',surveys:'用综述建立知识坐标，让新论文有迹可循。',saved:'把值得继续思考的论文，留在这里。',jobs:'采集与分析在后台进行，不打断你的阅读。',settings:'连接模型，定义你的研究边界。',notes:'从阅读到思考，让知识在笔记之间生长。',trends:'在更长的时间里，观察研究方向的增长与转折。'})[page]}</p></div>{['overview','papers','map'].includes(page)&&<div className="heading-actions"><button className="button" onClick={()=>setImporting(true)}><Upload size={16}/>导入文献</button><button className="button primary" onClick={()=>setExploring(true)}><Compass size={17}/>论文探索</button></div>}</div>
    {error&&<div className="notice error"><TriangleAlert size={18}/>{(error as Error).message}<button onClick={()=>qc.invalidateQueries()}>重试</button></div>}
    {['overview','papers','map','saved','surveys'].includes(page)&&<div className="filter-bar"><div className="filter-group"><SlidersHorizontal size={16}/>{page==='map'?<DomainMultiSelect domains={domains.data||[]} selected={mapDomains} onChange={setMapDomains}/>:<select aria-label="选择研究领域" value={domain} onChange={e=>{setDomain(e.target.value);setFacet({})}}><option value="">全部研究领域</option>{domains.data?.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select>}</div>{!['saved','surveys'].includes(page)&&<div className="segments">{(['papers','map'].includes(page)?[7,30,90,0]:[7,30,90]).map(n=><button key={n} className={(page==='map'&&mapAllHistory?n===0:days===n)?'selected':''} onClick={()=>{setDays(n);if(page==='map')setMapAllHistory(n===0)}}>{n?`近 ${n} 天`:'全部时间'}</button>)}</div>}<span className="scope-note">arXiv 订阅范围</span></div>}

    {page==='projects'&&<Suspense fallback={<Loading/>}><Projects focus={projectTarget} onFocusChange={setProjectTarget} onPaper={setPaperId} onTrend={openTrend}/></Suspense>}
    {page==='trends'&&<Suspense fallback={<Loading/>}><Trends focus={trendTarget} onFocusChange={setTrendTarget} onProject={openProject}/></Suspense>}
    {exploring&&<ExplorationDialog domains={domains.data||[]} current={domain} onClose={()=>setExploring(false)} onSubmitted={()=>{qc.invalidateQueries({queryKey:['exploration-latest']});qc.invalidateQueries({queryKey:['jobs']});setToast('论文探索已开始，后台按检查点推进')}}/>}
    {page==='overview'&&<>
     <ExplorationStatus onPaper={setPaperId} onTrends={()=>navigate('trends')}/>
     {!settings.data?.has_key&&<div className="setup-banner"><div className="setup-symbol"><Sparkles size={24}/></div><div><strong>让每篇论文，找到它的研究坐标</strong><p>连接 DeepSeek，阅读综述并提取论文的方法、贡献与局限。</p></div><button className="button" onClick={()=>navigate('settings')}>连接模型 <ArrowRight size={16}/></button></div>}
     <div className="metrics"><Metric label={data?.announcements?"近期收录论文":"近期新增论文"} value={data?.total} icon={FileText} note={data?.announcements ? `包含 ${data.announcements} 篇 RSS 公告` : `按首次发表时间 · 近 ${days} 天`}/><Metric label="全文分析完成" value={data?.analyzed} icon={Sparkles} note="当前论文与分类版本"/><Metric label="已识别小方向" value={data?.topics.length} icon={Layers3} note="基于有证据的分类结果"/><Metric label="我的收藏" value={data?.saved} icon={Bookmark} note="当前筛选范围"/></div>
     <div className="chart-grid"><section className="panel"><PanelTitle title="研究活动" subtitle={data?.announcements ? '含公告日期；历史回填尚未完成' : '本地精读库的新增分布'} extra={<span className="legend"><i/>论文数量</span>}/>{data?.total?<Suspense fallback={<Loading/>}><Chart data={timeline}/></Suspense>:<Empty title="等候第一批新发现" description="探索后展示入选本地精读库的论文；全范围计数见领域趋势。" action={<button className="text-button" onClick={()=>setExploring(true)}>开始探索 <ArrowRight size={15}/></button>}/>}</section><section className="panel"><PanelTitle title={data?.topics.length?'研究方向':'来源分类'} subtitle={data?.topics.length?'点击方向，查看相关论文':'arXiv 原始分类 · 不代表 AI 分析'}/>{data?.total?<Suspense fallback={<Loading/>}><Chart type="bar" data={data.topics.length?data.topics:data.categories} onSelect={n=>drill(n,!!data.topics.length)}/></Suspense>:<Empty icon={Layers3} title="领域地图正在等待数据" description="采集后先显示来源分类，分析后呈现研究小方向。"/>}</section></div>
     <section className="panel latest"><PanelTitle title="最新进入视野" subtitle="先浏览摘要，再决定深入阅读" extra={<button className="text-button" onClick={()=>navigate('papers')}>全部论文 <ArrowUpRight size={16}/></button>}/>{list.isLoading?<Loading/>:list.data?.items.length?list.data.items.map(p=><PaperRow key={p.id} preview={false} paper={p} open={()=>setPaperId(p.id)} save={()=>bookmark(p)} onProject={openProject}/>):<Empty title="你的研究动态，从这里开始" description="研究领域已准备就绪。同步后，论文会自动进入这个列表。"/>}</section>
    </>}

    {(page==='papers'||page==='saved')&&<section className="panel paper-panel"><div className="list-toolbar"><div className="search-input"><Search size={18}/><input ref={searchRef} placeholder="搜索标题、摘要、作者或 arXiv 编号…" value={search} onChange={e=>setSearch(e.target.value)} aria-label="搜索标题或摘要"/>{search&&<button className="icon-button" aria-label="清除搜索" onClick={()=>setSearch('')}><X size={15}/></button>}</div><span>{list.data?.total??'—'} 篇论文</span></div>
    {debounced.trim()&&<div className="paper-search-options">
     <label>排序<select aria-label="搜索排序" value={searchSort} onChange={event=>setSearchSort(event.target.value as 'research'|'recent')}>
      <option value="research">匹配后按研究影响</option>
      <option value="recent">最新发表</option>
     </select></label>
     <span>多个词需同时匹配 · 研究影响来自本地引用与历史入选记录</span>
    </div>}
    {(facet.topic||facet.category)&&<div className="facet"><span>{facet.topic||facet.category}{facet.method?` · ${facet.method}`:null}</span><button aria-label="移除分类筛选" onClick={()=>setFacet({})}><X size={13}/></button></div>}{list.isLoading?<Loading/>:list.data?.items.length?list.data.items.map(p=><PaperRow key={p.id} paper={p} open={()=>setPaperId(p.id)} save={()=>bookmark(p)} onProject={openProject}/>):<Empty icon={page==='saved'?Bookmark:Search} title={search?'没有找到匹配论文':page==='saved'?'留住下一篇重要发现':'暂时没有论文'} description={search?'尝试更简短的关键词，或调整研究领域与时间范围。':page==='saved'?'在论文旁点击书签，即可加入收藏。':'点击论文探索，或选择更长的时间范围。'}/>}<div className="feed-end" ref={sentinel} aria-live="polite">{feed.isFetchingNextPage?<><LoaderCircle size={16} className="spin"/>正在加载更多论文</>:feed.isFetchNextPageError?<button className="button small" onClick={()=>feed.fetchNextPage()}>加载失败，点击重试</button>:feed.hasNextPage?<button className="text-button" onClick={()=>feed.fetchNextPage()}>继续加载</button>:list.data?.items.length?`已显示全部 ${list.data.items.length} 篇论文`:null}</div></section>}

    {page==='notes'&&<Suspense fallback={<Loading/>}><Notes/></Suspense>}
    {page==='map'&&<><MapSectionNav/><div id="map-taxonomy"><Suspense fallback={<Loading/>}><Hierarchy domain="" domainIds={mapDomains} days={mapAllHistory?0:days} onPaper={setPaperId}/></Suspense></div><div id="map-relations"><Suspense fallback={<Loading/>}><RelationGraph domain="" domainIds={mapDomains} days={days} allHistory={mapAllHistory} onHistoryChange={setMapAllHistory} onPaper={setPaperId}/></Suspense></div><div className="notice"><Compass size={19}/><span>应用方向与方法分别统计；一篇论文可有多个标签，标签计数之和可能大于论文总数。</span></div><div className="domain-cards">{(domains.data||[]).filter(d=>!mapDomains.length||mapDomains.includes(d.id)).map(d=><section className="domain-card" key={d.id}><div className="domain-card-top"><span className="domain-symbol" style={{color:swatch(d.color),background:'color-mix(in srgb, '+swatch(d.color)+' 8%, transparent)'}}><FlaskConical size={24}/></span><span className="tag">分类 v{d.taxonomy_version}</span></div><h2>{d.name}</h2><p>{d.description}</p><div className="topic-chips">{d.topics.map(t=><button key={t} onClick={()=>{setDomain(d.id);drill(t,true)}}>{t}<ArrowUpRight size={12}/></button>)}</div><footer><span>{d.count} 篇已采集</span><button className="text-button" onClick={()=>setEditDomain(d)}>编辑领域 <ArrowRight size={14}/></button></footer></section>)}</div><div id="map-methods"><Suspense fallback={<Loading/>}><MethodMatrix domain="" domainIds={mapDomains} days={mapAllHistory?0:days} onPaper={setPaperId}/></Suspense></div></>}

    {page==='surveys'&&<><div className="survey-intro"><div><span className="eyebrow">BUILD YOUR KNOWLEDGE BASE</span><h2>让综述成为研究地图的起点</h2><p>导入代表性综述，提取有原文依据的小方向定义。查看分类草稿后发布，新论文就能沿着这套坐标归类。</p><div className="steps"><span>01 导入综述</span><ArrowRight size={14}/><span>02 阅读与提取</span><ArrowRight size={14}/><span>03 发布分类</span></div></div><BookOpen className="survey-art" size={94} strokeWidth={1}/></div><SurveyUpload domains={domains.data||[]} current={domain} act={act}/><div className="survey-list">{surveys.isLoading?<Loading/>:surveys.data?.length?surveys.data.map(s=><section className="panel survey-item" id={"survey-"+s.id} key={s.id}><div className="survey-row"><FileText size={28}/><div><h3>{s.title}</h3><p>{domains.data?.find(d=>d.id===s.domain_id)?.name} · {date(s.created)}</p></div><span className="tag">{{uploaded:'已导入',draft:'待检查草稿',published:'已发布'}[s.status]}</span><a className="button small" href={`/api/surveys/${s.id}/file`} target="_blank" rel="noreferrer">原文 <ExternalLink size={14}/></a><button className="button small" onClick={()=>act(()=>api(`/surveys/${s.id}/analyze`,{method:'POST'}),'综述阅读已加入队列')} disabled={busy}>提取分类</button></div>{s.draft.topics&&<div className="draft-topics">{s.draft.topics.map(t=><div key={t.name}><strong>{t.name}</strong><p><MathText text={t.definition}/></p><details><summary>查看证据 · 第 {t.page} 页</summary><blockquote><MathText text={t.quote}/></blockquote></details></div>)}{s.status==='draft'&&<button className="button primary" onClick={()=>act(()=>api(`/surveys/${s.id}/publish`,{method:'POST'}),'已发布新版分类；旧分析仍然保留')}>发布为新版领域分类 <Check size={16}/></button>}</div>}</section>):<Empty icon={BookOpen} title="知识库还没有综述" description="支持 PDF，单个文件最多 25MB。导入后可随时阅读和生成分类草稿。"/>}</div></>}

    {page==='jobs'&&<Suspense fallback={<Loading/>}><JobsPage domains={domains.data||[]} domain={domain} onNotice={setToast}/></Suspense>}

    {page==='settings'&&<><AppearanceSettings/><Suspense fallback={<Loading/>}><WorkspacePanel/></Suspense><SettingsForm config={settings.data} act={act}/><Suspense fallback={<Loading/>}><ModelBudgetSettings onNotice={setToast}/></Suspense><section className="panel"><PanelTitle title="研究领域" subtitle="可添加任意学科；采集规则、分类和综述知识独立维护" extra={<button className="button small" onClick={()=>setEditDomain('new')}><Plus size={15}/>新增领域</button>}/>{domains.data?.map(d=><div className="settings-domain" key={d.id}><span className="domain-dot" style={{background:swatch(d.color)}}/><div><strong>{d.name}</strong><p>{d.description||d.query}</p></div><span className="tag">{d.auto_sync?'每日自动同步':'手动同步'}</span><button className="button small" onClick={()=>setEditDomain(d)}>编辑</button></div>)}</section><div className="notice"><CheckCircle2 size={18}/><span>文献与分析保存在本机。DeepSeek 密钥使用当前 Windows 用户加密保存；全文分析时会将论文文本发送给模型服务。</span></div></>}
    <footer className="page-footer"><span>Research Atlas <i/> 让发现有迹可循</span><span>数据来源 arXiv · 本地研究工作台</span></footer>
   </main></PageBoundary>
  </div>
  {toast&&<div role="status" className="toast"><span>{toast}</span><button className="icon-button" aria-label="关闭提示" onClick={()=>setToast('')}><X size={16}/></button></div>}
  {importing&&<PaperImport domains={domains.data||[]} current={domain} onClose={()=>setImporting(false)} onImported={()=>qc.invalidateQueries()} onOpen={(id,did)=>{setImporting(false);setDomain(did);setFacet({});setDays(0);setPage('papers');setPaperId(id)}}/>}
  {paperId&&<Suspense fallback={<Loading/>}><PaperDetail key={paperId} open={setPaperId} id={paperId} domain={['map','projects'].includes(page)?'':domain} domains={domains.data||[]} close={()=>setPaperId(null)} act={act} onProject={openProject}/></Suspense>}
  {editDomain&&<DomainForm value={editDomain} close={()=>setEditDomain(null)} act={act}/>}
 </div>;
}

function Metric({label,value,icon:Icon,note}:{label:string;value?:number;icon:typeof Compass;note:string}){return <div className="metric"><div><span>{label}</span><Icon size={18}/></div><strong>{value===undefined?'—':value.toLocaleString()}</strong><small>{note}</small></div>}
function PanelTitle({title,subtitle,extra}:{title:string;subtitle?:string;extra?:React.ReactNode}){return <div className="panel-title"><div><h2>{title}</h2>{subtitle&&<p>{subtitle}</p>}</div>{extra}</div>}

type Action=(fn:()=>Promise<unknown>,success:string)=>Promise<void>;
function DomainForm({value,close,act}:{value:Domain|'new';close:()=>void;act:Action}){
 const d=value==='new'?null:value;
 const [name,setName]=useState(d?.name||''),[description,setDescription]=useState(d?.description||''),[query,setQuery]=useState(d?.query||''),[topics,setTopics]=useState(d?.topics.join('，')||''),[auto,setAuto]=useState(d?.auto_sync??true),[saving,setSaving]=useState(false);
 async function submit(e:FormEvent){e.preventDefault();setSaving(true);await act(async()=>{await api(d?'/domains/'+d.id:'/domains',{method:d?'PUT':'POST',body:JSON.stringify({name,description,query,topics:topics.split(/[,，\n]/).map(t=>t.trim()).filter(Boolean),auto_sync:auto})});close()},'研究领域已保存');setSaving(false)}
 return <Modal title={d?'编辑研究领域':'新增研究领域'} onClose={close}><form onSubmit={submit} className="form"><label>领域名称<input required value={name} onChange={e=>setName(e.target.value)} placeholder="例如：经济学、天文学、机器人" maxLength={60}/></label><label>研究重点<input value={description} onChange={e=>setDescription(e.target.value)} placeholder="描述你想持续关注的内容" maxLength={300}/></label><label>arXiv 订阅规则<textarea aria-label="arXiv 订阅规则" required value={query} onChange={e=>setQuery(e.target.value)} placeholder={'例如：cat:cs.RO 或 cat:econ.EM'} rows={3}/><small>支持 arXiv 查询语法。组合示例：cat:cs.RO AND all:"planning"</small></label><label>初始小方向<textarea value={topics} onChange={e=>setTopics(e.target.value)} placeholder="用逗号分隔；也可以稍后从综述提取" rows={2}/></label><label className="checkbox"><input type="checkbox" checked={auto} onChange={e=>setAuto(e.target.checked)}/>每天自动同步近期论文</label><div className="form-actions"><button type="button" className="button" onClick={close}>取消</button><button className="button primary" disabled={saving}>{saving?<LoaderCircle className="spin" size={16}/>:<Check size={16}/>}保存领域</button></div></form></Modal>;
}


function SurveyUpload({domains,current,act}:{domains:Domain[];current:string;act:Action}){
 const [did,setDid]=useState(current||domains[0]?.id||''),[file,setFile]=useState<File|null>(null),[saving,setSaving]=useState(false);const ref=useRef<HTMLInputElement>(null);
 useEffect(()=>{if(current)setDid(current);else if(!did&&domains[0])setDid(domains[0].id)},[current,domains,did]);
 return <form className="upload-strip" onSubmit={async e=>{e.preventDefault();if(!file)return;setSaving(true);const body=new FormData();body.append('domain_id',did);body.append('file',file);await act(async()=>{await api('/surveys',{method:'POST',body});setFile(null);if(ref.current)ref.current.value=''},'综述已导入，可开始提取分类');setSaving(false)}}><Upload size={22}/><select aria-label="综述所属领域" value={did} onChange={e=>setDid(e.target.value)} required>{domains.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select><input ref={ref} type="file" accept="application/pdf,.pdf" aria-label="选择综述 PDF" onChange={e=>setFile(e.target.files?.[0]||null)}/><button className="button primary" disabled={!file||saving}>{saving?<LoaderCircle size={16} className="spin"/>:<Plus size={16}/>}导入综述</button></form>;
}



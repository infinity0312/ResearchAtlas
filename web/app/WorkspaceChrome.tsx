import {useEditionSwatch} from '../ui/industrial/colors';
import {type RefObject} from 'react';
import {BriefcaseBusiness,Activity,FolderOpen,Menu,Settings2,X,Plus,ChevronRight,Search,Compass,LayoutDashboard,Network,TrendingUp,BookOpen,Bookmark,NotebookPen} from 'lucide-react';
import {type Domain} from '../api';
import {pageLabels as labels,type Page} from './useWorkspaceRoute';
const pages:{id:Page;label:string;icon:typeof Compass}[]=[{id:'projects',label:'研发项目',icon:BriefcaseBusiness},{id:'overview',label:'研究概览',icon:LayoutDashboard},{id:'papers',label:'发现论文',icon:Compass},{id:'map',label:'领域地图',icon:Network},{id:'trends',label:'领域趋势',icon:TrendingUp},{id:'surveys',label:'综述知识库',icon:BookOpen},{id:'saved',label:'我的收藏',icon:Bookmark},{id:'notes',label:'笔记系列',icon:NotebookPen}];
type NavProps={navRef:RefObject<HTMLElement|null>;compact:boolean;navOpen:boolean;setNavOpen:(value:boolean)=>void;page:Page;domain:string;domains:Domain[];navigate:(page:Page)=>void;onDomain:(id:string)=>void;onAddDomain:()=>void;running:number;worker:boolean;onOpenData:()=>void};
export function WorkspaceSidebar({navRef,compact,navOpen,setNavOpen,page,domain,domains,navigate,onDomain,onAddDomain,running,worker,onOpenData}:NavProps){const swatch=useEditionSwatch();return (
  <aside ref={navRef} id="workspace-navigation" className="sidebar" inert={compact&&!navOpen} aria-label="工作台导航" onKeyDown={e=>{if(!compact||!navOpen||e.key!=='Tab')return;const els=navRef.current?.querySelectorAll<HTMLElement>('button,a[href]');if(!els?.length)return;const first=els[0],last=els[els.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}}}>
   <button className="mobile-nav-close icon-button" aria-label="关闭导航" onClick={()=>setNavOpen(false)}><X size={20}/></button>
   <a className="brand" href="#" onClick={e=>{e.preventDefault();navigate('overview')}}><img src="/favicon.svg?v=2" alt=""/><span>Research Atlas<small>研发证据工作台</small></span></a>
   <div className="workspace"><span className="avatar">R</span><span>本机研究空间<small>Local workspace</small></span><span className="workspace-dot"/></div>
   <div className="nav-label">工作台</div><nav>{pages.map(({id,label,icon:Icon})=><button key={id} title={label} aria-label={label} aria-current={page===id?'page':undefined} className={'nav-item '+(page===id?'active':'')} onClick={()=>navigate(id)}><Icon size={19}/><span>{label}</span>{id==='papers'&&<span className="tiny-arrow">↗</span>}</button>)}</nav>
   <div className="nav-label domains-label">研究领域<button className="icon-button" aria-label="添加研究领域" onClick={onAddDomain}><Plus size={15}/></button></div>
   <div className="domain-nav">{domains.map(d=><button key={d.id} className={page==='papers'&&domain===d.id?'selected':''} onClick={()=>onDomain(d.id)} title={d.name}><i style={{background:swatch(d.color)}}/><span>{d.name}</span><small>{d.count}</small></button>)}</div>
   <div className="sidebar-bottom"><button className={'nav-item '+(page==='jobs'?'active':'')} onClick={()=>navigate('jobs')} title="后台任务"><Activity size={19}/><span>后台任务</span>{running>0&&<b className="count">{running}</b>}</button><button className={'nav-item '+(page==='settings'?'active':'')} onClick={()=>navigate('settings')} title="设置"><Settings2 size={19}/><span>设置与连接</span></button><button className="nav-item" onClick={onOpenData}><FolderOpen size={19}/><span>本地数据</span></button><div className="local-status"><span className={worker?'status-dot':'status-dot amber'}/><span>{worker?'本地工作台 · 后台在线':'本地工作台 · 后台未就绪'}</span></div></div>
  </aside>
)}
type HeaderProps={navToggle:RefObject<HTMLButtonElement|null>;navOpen:boolean;setNavOpen:(value:boolean)=>void;page:Page;onSearch:()=>void};
export function WorkspaceHeader({navToggle,navOpen,setNavOpen,page,onSearch}:HeaderProps){return (
<header className="topbar"><button ref={navToggle} className="mobile-nav-toggle icon-button" aria-label="展开导航" aria-expanded={navOpen} aria-controls="workspace-navigation" onClick={()=>setNavOpen(true)}><Menu size={21}/></button><div className="breadcrumb">我的空间 <ChevronRight size={14}/><strong>{labels[page]}</strong></div><div className="top-actions"><button className="search-shortcut" onClick={onSearch}><Search size={16}/><span>搜索论文</span><kbd>Ctrl K</kbd></button><span className="top-avatar">R</span></div></header>
)}


import {useId,useRef,useState} from 'react';
import {ArrowUpRight,Bookmark,ChevronDown,FileText} from 'lucide-react';
import {date,type Paper} from './api';
import MathText from './MathText';
import AnalysisQuality from './AnalysisQuality';
import './research-workflow.css';
import PaperProjectActions from './product/PaperProjectActions';
import type {ProjectFocus} from './product/projectNavigation';

export default function PaperLibraryRow({paper:p,open,save,preview=true,onProject}:{paper:Paper;open:()=>void;save:()=>void;preview?:boolean;onProject?:(target:ProjectFocus|null)=>void}){
 const [expanded,setExpanded]=useState(false),id=useId(),trigger=useRef<HTMLButtonElement>(null);
 const toggle=()=>setExpanded(v=>!v);
 const collapse=()=>{const node=trigger.current,top=node?.getBoundingClientRect().top;setExpanded(false);requestAnimationFrame(()=>{if(node&&top!==undefined){window.scrollBy({top:node.getBoundingClientRect().top-top,behavior:'instant'});node.focus({preventScroll:true})}})};
 return <article className={'paper-row'+(expanded?' paper-row-expanded':'')} data-paper-id={p.id}>
  <div className="paper-mark"><FileText size={20}/></div>
  <div className="paper-body">
   <div className="paper-meta"><span>{p.categories[0]}</span><i/> {date(p.published)}{p.date_basis==='announcement'?' 公告':p.date_basis==='imported'?' 导入':null}<span className="version">v{p.version}</span>{p.analysis&&<span className="analyzed">{p.analysis.version===p.version?'已分析':'旧版本分析'}</span>}{p.analysis&&<AnalysisQuality quality={p.analysis.quality} compact/>}</div>
   <button className="paper-title" onClick={open}><MathText text={p.title}/></button>
   {p.search_rank&&<p className="paper-search-rank">
    {p.search_rank.exact_id?'编号精确匹配':p.search_rank.title_hits?`题名命中 ${p.search_rank.title_hits}/${p.search_rank.terms}`:'其他题录字段命中'}
    {p.search_rank.curation_reason&&` · 入选依据：${p.search_rank.curation_reason}`}
    {p.search_rank.local_citations>0&&` · ${p.search_rank.local_citations} 篇本地论文引用`}
   </p>}
   {!expanded&&<p className="abstract"><MathText text={p.analysis?.summary||p.abstract} legacy={!!p.analysis}/></p>}
   <div className="paper-bottom"><span>{p.authors.slice(0,3).join(' · ')}{p.authors.length>3?' 等':''}</span><div>{(p.analysis?.topics||[]).slice(0,2).map(t=><span className="tag" key={t}>{t}</span>)}</div></div>
   {preview&&<button ref={trigger} type="button" className="paper-brief-toggle" aria-expanded={expanded} aria-controls={id} onClick={toggle}>摘要与分析概要 <ChevronDown size={14}/></button>}
   {preview&&expanded&&<section id={id} className="paper-inline-brief" aria-label={p.title+'的摘要与分析概要'} onKeyDown={event=>{if(event.key==='Escape'&&!(event.target as HTMLElement).closest('[role=dialog]')){event.preventDefault();event.stopPropagation();collapse()}}}>
    <div className="paper-brief-section"><span className="paper-brief-label">作者摘要 · 原文</span><p><MathText text={p.abstract}/></p></div>
    {p.analysis&&<div className="paper-brief-section"><span className="paper-brief-label">分析概要 · 论文 v{p.analysis.version}{p.analysis.version!==p.version?' · 旧版本':''}</span><p><MathText text={p.analysis.summary} legacy/></p>{p.analysis.methods.length>0&&<div className="paper-brief-methods">{p.analysis.methods.map(method=><span key={method}>{method}</span>)}</div>}</div>}
    <div className="paper-brief-footer"><button className="button small" onClick={open}>进入全文阅读 <ArrowUpRight size={14}/></button>{onProject&&<PaperProjectActions paper={p} onOpenProject={onProject}/>}<button className="text-button" onClick={collapse}>收起概要</button><span>{p.id} · {p.authors.length} 位作者</span></div>
   </section>}
  </div>
  <button className={'icon-button bookmark '+(p.saved?'is-saved':'')} aria-label={p.saved?'取消收藏':'收藏论文'} onClick={save}><Bookmark size={19} fill={p.saved?'currentColor':'none'}/></button>
  <button className="icon-button open-paper" aria-label="打开论文" onClick={open}><ArrowUpRight size={18}/></button>
 </article>;
}

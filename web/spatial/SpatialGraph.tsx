import {lazy,Suspense,useEffect,useRef,useState} from 'react';
import {ArrowUpRight,X} from 'lucide-react';
import {useAppearance} from '../ui/Appearance';
import type {GraphData} from '../GraphCanvas';
import {ResearchScene} from './ResearchScene';
import './spatial.css';
import './relief.css';
const GraphCanvas=lazy(()=>import('../GraphCanvas'));
export default function SpatialGraph({data,onPaper}:{data:GraphData;onPaper:(id:string)=>void}){
 const {appearance,reduced}=useAppearance(),host=useRef<HTMLDivElement>(null),scene=useRef<ResearchScene|null>(null),open=useRef(onPaper);open.current=onPaper;
 const [selected,setSelected]=useState<string|null>(null),[failed,setFailed]=useState(false),[ready,setReady]=useState(false);
 useEffect(()=>{if(failed)return;let disposed=false,worker:Worker|null=null;const el=host.current!;setReady(false);setSelected(null);
 try{const instance=new ResearchScene(el,data,setSelected,id=>open.current(id),()=>{if(!disposed)setFailed(true)},reduced,appearance.quality);scene.current=instance;
 const degree=new Map<string,number>();for(const e of data.relations||[]){degree.set(e.source_id,(degree.get(e.source_id)||0)+1);degree.set(e.target_id,(degree.get(e.target_id)||0)+1)}
 worker=new Worker(new URL('../graph-layout.worker.ts',import.meta.url),{type:'module'});worker.onmessage=e=>{if(disposed)return;instance.setPositions(e.data.positions);setReady(true)};worker.onerror=()=>{if(!disposed)setReady(true)};
 worker.postMessage({nodes:data.papers.map(p=>({id:'p:'+p.id,label:p.label||p.title.slice(0,18),degree:degree.get(p.id)||0})),links:(data.relations||[]).map(e=>({source:'p:'+e.source_id,target:'p:'+e.target_id,weight:1})),reducedMotion:reduced});
 }catch{setFailed(true)}
 return()=>{disposed=true;worker?.terminate();scene.current?.dispose();scene.current=null};
 },[data,failed,reduced,appearance.quality]);
 useEffect(()=>{scene.current?.select(selected)},[selected]);
 const paper=data.papers.find(p=>p.id===selected),relations=(data.relations||[]).filter(e=>e.source_id===selected||e.target_id===selected);
 function move(delta:number){const i=data.papers.findIndex(p=>p.id===selected);setSelected(data.papers[(i<0?(delta>0?0:data.papers.length-1):(i+delta+data.papers.length)%data.papers.length)]?.id||null)}
 if(failed)return <><p className="spatial-fallback" role="status">空间渲染暂不可用，已切换到基础关系图。</p><Suspense fallback={<div className="empty">正在加载关系图…</div>}><GraphCanvas data={data} similarity={false} onPaper={onPaper}/></Suspense></>;
 return <section className={'spatial-network '+(paper?'is-selected':'')} aria-label="论文空间关系" data-ready={ready}>
 <div className="relief-toolbar"><button className="button small" aria-label="放大空间图谱" onClick={()=>scene.current?.zoom(.8)}>放大</button><button className="button small" aria-label="缩小空间图谱" onClick={()=>scene.current?.zoom(1.25)}>缩小</button><button className="button small" aria-label="适应空间画布" onClick={()=>scene.current?.fit()}>全览</button></div>
 <div className="spatial-stage" ref={host} tabIndex={0} aria-label="空间画布，左右方向键切换论文，Enter 阅读，Escape 取消选择" onKeyDown={e=>{if(['ArrowLeft','ArrowRight','Enter','Escape'].includes(e.key))e.preventDefault();if(e.key==='ArrowLeft')move(-1);if(e.key==='ArrowRight')move(1);if(e.key==='Enter'&&selected)onPaper(selected);if(e.key==='Escape')setSelected(null)}}/>
 <div className="spatial-overline"><span>KNOWLEDGE / IN SPACE</span><span>{String(data.papers.length).padStart(3,'0')} PAPERS · {data.relations?.length||0} RELATIONS</span></div>
 {!ready&&<div className="spatial-loading" role="status">正在构建论文关系空间…</div>}

 {paper?<aside className="spatial-evidence" key={paper.id}><header><span>FOCUS / {String(data.papers.indexOf(paper)+1).padStart(3,'0')}</span><button aria-label="取消空间聚焦" onClick={()=>setSelected(null)}><X size={17}/></button></header><h3>{paper.label||paper.title}</h3><p>{paper.title}</p><div className="spatial-paper-meta">{paper.published?.slice(0,10)||'日期待补全'}<span>{relations.length} 条有据关系</span></div><button className="spatial-read" onClick={()=>onPaper(paper.id)}>进入论文阅读 <ArrowUpRight size={17}/></button><div className="spatial-evidence-list">{relations.slice(0,8).map(e=>{const id=e.source_id===paper.id?e.target_id:e.source_id,p=data.papers.find(p=>p.id===id);return <button key={e.id} onClick={()=>setSelected(id)} title={e.evidence.quote}><span>{({cites:['引用','被引用'],extends:['继承','被继承'],improves:['改进','被改进']} as Record<string,string[]>)[e.kind]?.[e.source_id===paper.id?0:1]||'关联'}</span><strong>{p?.label||p?.title||id}</strong><small>原文第 {e.evidence.page} 页 · {e.evidence.quote.slice(0,105)}</small></button>})}{!relations.length&&<p>暂未建立经过原文核验的关系。</p>}</div></aside>:null}

 </section>
}

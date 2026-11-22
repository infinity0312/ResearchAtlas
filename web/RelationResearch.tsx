import {useState} from 'react';
import type {GraphData} from './GraphCanvas';
import './graph-research.css';

const relationLabels:Record<string,string> = {cites:'引用',extends:'继承',improves:'改进'};

export function focusedRelationData(data:GraphData, id:string):GraphData {
 if (!id) return data;
 const relations=(data.relations||[]).filter(r=>r.source_id===id||r.target_id===id);
 const papers=new Set([id,...relations.flatMap(r=>[r.source_id,r.target_id])]);
 return {...data,relations,papers:data.papers.filter(p=>papers.has(p.id)),links:data.links.filter(l=>papers.has(l.paper_id))};
}

export default function RelationResearch({data,focus,onFocus,onPaper}:{
 data:GraphData;focus:string;onFocus:(id:string)=>void;onPaper:(id:string)=>void;
}){
 const [direction,setDirection]=useState<'incoming'|'outgoing'>('incoming');
 const relations=data.relations||[];
 const titles=new Map(data.papers.map(p=>[p.id,p.title]));
 const degrees=new Map<string,number>();
 for(const r of relations) {
  degrees.set(r.source_id,(degrees.get(r.source_id)||0)+1);
  degrees.set(r.target_id,(degrees.get(r.target_id)||0)+1);
 }
 const ordered=[...data.papers].sort((a,b)=>(degrees.get(b.id)||0)-(degrees.get(a.id)||0)||a.title.localeCompare(b.title));
 const incoming=relations.filter(r=>r.target_id===focus);
 const outgoing=relations.filter(r=>r.source_id===focus);
 const active=direction==='incoming'?incoming:outgoing;
 const counts=Object.entries(relationLabels).map(([key,label])=>[label,relations.filter(r=>r.kind===key).length] as const);
 return <section className="graph-research" aria-label="引用追溯">
  <div className="graph-research-line">
   <label>追溯论文<select aria-label="追溯论文" value={focus} onChange={event=>onFocus(event.target.value)}>
    <option value="">查看全局关系</option>{ordered.map(p=><option key={p.id} value={p.id}>{p.title} · {degrees.get(p.id)||0} 条连接</option>)}
   </select></label>
   <span>{counts.map(([label,n])=>`${label} ${n}`).join(' · ')} · {degrees.size}/{data.papers.length} 篇有连接</span>
  </div>
  {focus?<div className="graph-research-result">
   <div className="graph-research-actions" role="group" aria-label="引用方向">
    <button className="button small" aria-pressed={direction==='incoming'} onClick={()=>setDirection('incoming')}>指向此篇 · {incoming.length}</button>
    <button className="button small" aria-pressed={direction==='outgoing'} onClick={()=>setDirection('outgoing')}>此篇指向 · {outgoing.length}</button>
    <button className="text-button" onClick={()=>onPaper(focus)}>阅读所选论文 ↗</button>
   </div>
   {active.length?<details open key={focus+direction} className="graph-research-list"><summary>{active.length} 条关系的出处</summary><ul>
    {active.map(r=>{
     const neighbor=direction==='incoming'?r.source_id:r.target_id;
     const version=r.evidence.version;
     return <li key={r.id}>
      <details><summary>{relationLabels[r.kind]||r.kind} · {titles.get(neighbor)||neighbor} · 来源第 {r.evidence.page} 页</summary>
       <blockquote>{r.evidence.quote}</blockquote>
       <div className="graph-research-actions">
        <button className="text-button" onClick={()=>onFocus(neighbor)}>沿此关系继续追溯</button>
        {version?<a className="text-button" href={`/api/paper/pdf?id=${encodeURIComponent(r.source_id)}&version=${version}#page=${r.evidence.page}`} target="_blank" rel="noreferrer">核对引用者原页 ↗</a>:<button className="text-button" onClick={()=>onPaper(r.source_id)}>阅读关系来源 ↗</button>}
       </div>
      </details>
     </li>;
    })}
   </ul></details>:<p>当前范围内暂无这个方向的关系记录。</p>}
  </div>:!relations.length?<p>当前范围没有已核对的关系。可在相似度图查分类邻近，在时间脉络看题录日期。</p>:null}
 </section>;
}

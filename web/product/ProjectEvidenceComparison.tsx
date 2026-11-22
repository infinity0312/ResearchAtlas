import {useState} from 'react';
import type {Criterion,Evidence} from './projectApi';
import '../research-workflow.css';

const stance={supports:'支持',contradicts:'反对',uncertain:'待核'};

function EvidencePair({rows,onEvidence}:{rows:Evidence[];onEvidence:(id:string)=>void}){
 const [leftId,setLeftId]=useState(rows[0].id);
 const [rightId,setRightId]=useState(()=>rows.find(row=>row.paper_id!==rows[0].paper_id)?.id||'');
 const left=rows.find(row=>row.id===leftId);
 const right=rows.find(row=>row.id===rightId);
 const options=(e:Evidence)=>`${e.snapshot.paper_title} · v${e.snapshot.paper_version} · 第 ${e.snapshot.page} 页 · ${stance[e.stance]}`;
 return <>
  <div className="project-evidence-comparison-columns">
   <label>第一篇依据<select value={leftId} onChange={event=>setLeftId(event.target.value)}>
    <option value="">选择依据</option>{rows.map(e=><option key={e.id} value={e.id}>{options(e)}</option>)}
   </select></label>
   <label>第二篇依据<select value={rightId} onChange={event=>setRightId(event.target.value)}>
    <option value="">选择依据</option>{rows.map(e=><option key={e.id} value={e.id}>{options(e)}</option>)}
   </select></label>
  </div>
  {left&&right&&left.paper_id!==right.paper_id?<div className="project-evidence-comparison-columns">
   {[left,right].map(e=><article key={e.id}>
    <strong>{e.snapshot.paper_title}</strong>
    <p>{stance[e.stance]} · {e.health.eligible?'当前有效':'待复核'}</p>
    <p>{e.snapshot.claim_text}</p>
    <p>适用条件：{e.context||'未记录'}</p>
    <button className="text-button" onClick={()=>onEvidence(e.id)}>核对原文与绑定版本</button>
   </article>)}
  </div>:<p>请选择同一标准下来自两篇不同论文的依据。</p>}
 </>;
}

export default function ProjectEvidenceComparison({criteria,evidence,onEvidence}:{criteria:Criterion[];evidence:Evidence[];onEvidence:(id:string)=>void}){
 const [selection,setSelection]=useState('');
 const available=criteria.map(criterion=>({
  ...criterion, rows:evidence.filter(e=>e.criterion_id===criterion.id),
 })).filter(criterion=>new Set(criterion.rows.map(e=>e.paper_id)).size>=2);
 const active=available.find(criterion=>criterion.id===selection)||available[0];
 if(!active)return null;
 return <details className="project-evidence-comparison">
  <summary>并排核对两篇论文的依据</summary>
  <p>按同一评价标准查看主张、立场和适用条件。量化比较前，请核对实验对象、指标和协议。</p>
  <label>对照标准<select value={active.id} onChange={event=>setSelection(event.target.value)}>
   {available.map(criterion=><option key={criterion.id} value={criterion.id}>{criterion.label}</option>)}
  </select></label>
  <EvidencePair key={active.id} rows={active.rows} onEvidence={onEvidence}/>
 </details>;
}

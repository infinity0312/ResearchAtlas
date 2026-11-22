import {useState,type FormEvent} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {ExternalLink} from 'lucide-react';
import {api,params} from '../api';
import type {Project} from './projectApi';
import './agentarts-review.css';

type Finding={evidence_id:string;stance:'supports'|'contradicts'|'uncertain';reason:string};
type Assessment={criterion_id:string;label:string;status:'supported'|'contradicted'|'mixed'|'insufficient';findings:Finding[];next_step:string};
type Source={evidence_id:string;paper_id:string;paper_version:number;title:string;pdf_page:number;quote:string};
type Review={
 id:string;state:'running'|'ready'|'failed'|'no_evidence';query:string;project_revision:number;
 expected_revision:number;stale:boolean;execution_id:string|null;error:string;
 sources:Source[];assessments:Assessment[];bindings:Record<string,string>;
};
type Status={enabled:boolean;configured:boolean;review:Review|null};
const labels={supported:'有支持依据',contradicted:'有反对依据',mixed:'正反依据并存',insufficient:'证据不足'};
const stances={supports:'支持',contradicts:'反对',uncertain:'待核'};

export default function AgentArtsReview({project,disabled}:{project:Project;disabled:boolean}){
 const qc=useQueryClient();
 const path='/projects/'+encodeURIComponent(project.id)+'/agentarts';
 const key=['agentarts-review',project.id];
 const status=useQuery({
  queryKey:key,queryFn:()=>api<Status>(path),
  refetchInterval:state=>state.state.data?.review?.state==='running'?2500:false,
 });
 const [query,setQuery]=useState<string|null>(null);
 const [active,setActive]=useState(false);
 const [error,setError]=useState('');
 const result=status.data?.review;
 const queryInput=query??result?.query??'';

 async function run(endpoint:string,body:object,refreshProject=false){
  setActive(true);
  setError('');
  try{
   const review=await api<Review>(endpoint,{method:'POST',body:JSON.stringify(body)});
   qc.setQueryData<Status>(key,old=>old?{...old,review}:old);
   if(refreshProject)await Promise.all([
    qc.invalidateQueries({queryKey:['project',project.id]}),
    qc.invalidateQueries({queryKey:['projects']}),
    qc.invalidateQueries({queryKey:['project-impacts']}),
   ]);
  }catch(err){
   setError(err instanceof Error?err.message:'评审请求未完成');
   await qc.invalidateQueries({queryKey:key});
  }finally{setActive(false)}
 }

 function submit(event:FormEvent){
  event.preventDefault();
  void run(path,{revision:project.revision,query:queryInput.trim()});
 }

 if(!status.data?.enabled)return null;
 const working=active||result?.state==='running';
 const unavailable=disabled||working;
 const stale=!!result&&(result.stale||result.expected_revision!==project.revision);
 return <section className="agentarts-review" aria-label="AgentArts 证据评审" aria-busy={working}>
  <header>
   <div className="eyebrow">AGENTARTS / EVIDENCE REVIEW</div>
   <h3>发起证据评审</h3>
   <p>将项目评价标准与获准的文献片段送入工作流，生成供人工核对的草稿。</p>
  </header>
  <form className="agentarts-review-form" onSubmit={submit}>
   <label>检索关键词<input type="search" required maxLength={160} placeholder="例如：thermal conductivity" value={queryInput} onChange={e=>setQuery(e.target.value)}/></label>
   <button className="button primary" disabled={unavailable||!queryInput.trim()||!status.data.configured}>{working?'正在评审…':'运行 AgentArts 评审'}</button>
  </form>
  {!status.data.configured&&<p role="status">此演示项目尚未配置已发布的 AgentArts 工作流。</p>}
  {result?.state==='running'&&<p role="status">等待工作流返回。若运行长时间中断，可重新发起评审。</p>}
  {error&&<p className="notice error" role="alert">{error}</p>}
  {result?.state==='failed'&&<p className="notice error" role="alert">{result.error}</p>}
  {result?.state==='no_evidence'&&<p className="notice" role="status">演示语料中未找到可核对的匹配片段，本次检查在本机结束。</p>}
  {!!result?.assessments.length&&<div className="agentarts-assessments">
   <p className="muted">基于项目修订 {result.project_revision} 的草稿{result.execution_id&&<> · 执行记录 <code>{result.execution_id}</code></>}</p>
   {stale&&<p className="notice" role="status">项目修订已变化。可回看这份草稿，采纳前需重新评审。</p>}
   {result.assessments.map(row=><article key={row.criterion_id}>
    <h4>{row.label} <span className="tag">{labels[row.status]}</span></h4>
    <p>{row.next_step}</p>
    {row.findings.map(finding=>{
     const source=result.sources.find(item=>item.evidence_id===finding.evidence_id);
     if(!source)return null;
     const bound=result.bindings[row.criterion_id+':'+source.evidence_id];
     const href='/api/paper/pdf?'+params({id:source.paper_id,version:source.paper_version})+'#page='+source.pdf_page;
     return <details key={source.evidence_id} className="agentarts-finding">
      <summary><strong>{stances[finding.stance]}</strong> {source.title} · v{source.paper_version} / 第 {source.pdf_page} 页</summary>
      <blockquote>{source.quote}</blockquote>
      <p>{finding.reason}</p>
      <div className="agentarts-finding-actions">
       <a className="text-button" href={href} target="_blank" rel="noreferrer">查看该版本原页 <ExternalLink size={13}/></a>
       {bound?<span className="tag">已采纳</span>:<button type="button" className="button small" disabled={unavailable||stale||finding.stance==='uncertain'} onClick={()=>void run(path+'/'+result.id+'/bind',{
        revision:project.revision,criterion_id:row.criterion_id,evidence_id:source.evidence_id,
       },true)}>采纳此证据</button>}
      </div>
     </details>;
    })}
   </article>)}
  </div>}
 </section>;
}

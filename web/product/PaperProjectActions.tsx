import {useState} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {ArrowUpRight,FolderPlus} from 'lucide-react';
import {api} from '../api';
import Modal from '../Modal';
import {projectApi,type Project} from './projectApi';
import {projectHref,type ProjectFocus} from './projectNavigation';
import './paper-project-actions.css';

type Candidate={id:string;status:'pending'|'kept'|'excluded';reason:string};
type PaperLink={project_id:string;title:string;candidate:Candidate|null;evidence:{id:string;criterion_label:string;eligible:boolean}[]};
const statusLabel={pending:'待筛选',kept:'保留线索',excluded:'已排除'};

export default function PaperProjectActions({paper,onOpenProject,showLinks=false}:{paper:{id:string;title:string};onOpenProject:(target:ProjectFocus|null)=>void;showLinks?:boolean}){
 const qc=useQueryClient(),[opened,setOpened]=useState(false),[projectId,setProjectId]=useState(''),[reason,setReason]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[saved,setSaved]=useState<{candidate:Candidate;projectId:string;existing:boolean}|null>(null);
 const projects=useQuery({queryKey:['projects'],queryFn:projectApi.list,enabled:opened,staleTime:0});
 const links=useQuery({queryKey:['paper-projects',paper.id],queryFn:()=>api<{items:PaperLink[]}>('/projects/paper-links?paper_id='+encodeURIComponent(paper.id)),enabled:showLinks||opened,staleTime:0});
 const selectedId=projectId||projects.data?.items[0]?.id||'',existing=links.data?.items.find(item=>item.project_id===selectedId)?.candidate;
 const go=(target:ProjectFocus|null)=>{setOpened(false);onOpenProject(target)};
 async function add(){if(!selectedId)return;setBusy(true);setError('');try{const candidate=await api<Candidate>(`/projects/${encodeURIComponent(selectedId)}/candidates`,{method:'POST',body:JSON.stringify({paper_id:paper.id,reason})});setSaved({candidate,projectId:selectedId,existing:!!existing});setReason('');await Promise.all([qc.invalidateQueries({queryKey:['project-candidates',selectedId]}),qc.invalidateQueries({queryKey:['paper-projects',paper.id]}),qc.invalidateQueries({queryKey:['project',selectedId]})])}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <>
  <button type="button" className="button small paper-project-add" onClick={()=>{setOpened(true);setSaved(null);setError('')}}><FolderPlus size={14}/>加入项目线索</button>
  {showLinks&&<section className="paper-project-links" aria-label="论文关联项目">
   <div className="paper-project-caption"><span>项目关联</span><small>候选线索与正式证据分别记录</small></div>
   {links.isLoading?<p>正在核对项目关联…</p>:links.isError?<p role="alert">项目关联暂未载入。<button className="text-button" onClick={()=>links.refetch()}>重试</button></p>:links.data?.items.length?<ul>{links.data.items.map(item=><li key={item.project_id}><div><strong>{item.title}</strong><span>{item.candidate?statusLabel[item.candidate.status]:'正式证据'}{item.evidence.length?` · ${item.evidence.length} 条绑定，其中 ${item.evidence.filter(e=>e.eligible).length} 条当前有效`:''}</span></div><button className="text-button" onClick={()=>go({id:item.project_id,...(item.evidence[0]?{evidenceId:item.evidence[0].id}:item.candidate?{candidateId:item.candidate.id}:{})})}>查看项目 <ArrowUpRight size={13}/></button></li>)}</ul>:<p>尚未用于研发项目。阅读中发现值得验证的方向时，可先加入线索。</p>}
  </section>}
  {opened&&<Modal title="加入项目线索" onClose={()=>{if(!busy)setOpened(false)}} className="paper-project-modal"><div className="paper-project-modal-body">
   <p className="paper-project-paper">{paper.title}</p><p className="paper-project-explainer">先记录与决策的关联；加入线索不代表已核验，也不会自动绑定证据或发起模型分析。</p>
   {saved?<div className="paper-project-result" role="status"><h3>{saved.existing?'项目已有此线索':'已加入项目线索'}</h3><p>{saved.existing?'原有状态与理由已保留。可进入项目查看并继续筛选。':'项目中可记录保留或排除理由，再选择可核查的主张作为正式证据。'}</p><a className="button primary" href={projectHref({id:saved.projectId,candidateId:saved.candidate.id})} onClick={e=>{if(!e.metaKey&&!e.ctrlKey&&!e.shiftKey&&!e.altKey){e.preventDefault();go({id:saved.projectId,candidateId:saved.candidate.id})}}}>前往项目处理 <ArrowUpRight size={14}/></a><button className="text-button" onClick={()=>setOpened(false)}>继续阅读</button></div>:<>
    {projects.isLoading?<p>正在载入项目…</p>:projects.isError?<p role="alert">{projects.error.message}<button className="text-button" onClick={()=>projects.refetch()}>重新载入项目</button></p>:projects.data?.items.length?<form onSubmit={e=>{e.preventDefault();void add()}}>
     <label>目标项目<select aria-label="目标项目" value={selectedId} onChange={e=>{setProjectId(e.target.value);setError('')}} disabled={busy}>{projects.data.items.map((p:Project)=><option key={p.id} value={p.id}>{p.title}</option>)}</select></label>
     {existing?<p className="notice">此论文已在项目中：{statusLabel[existing.status]}。再次加入会保留原有理由。</p>:<label>关联原因<textarea aria-label="关联原因" maxLength={5000} rows={3} placeholder="例如：测试工况与项目相近，需进一步核对性能边界。可暂留空。" value={reason} onChange={e=>setReason(e.target.value)} disabled={busy}/></label>}
     {error&&<p role="alert" className="notice error">{error}</p>}<div className="paper-project-submit"><button className="button primary" disabled={busy||!selectedId} type="submit">{busy?'正在加入…':'确认加入线索'}</button><button className="text-button" type="button" onClick={()=>setOpened(false)} disabled={busy}>取消</button></div>
    </form>:<div className="paper-project-result"><p>目前还没有研发项目。先定义一个决策问题，再把相关论文收进来。</p><button className="button primary" onClick={()=>go(null)}>创建研发项目 <ArrowUpRight size={14}/></button></div>}
   </>}
  </div></Modal>}
 </>;
}

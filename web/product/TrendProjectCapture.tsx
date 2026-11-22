import {useEffect,useRef,useState} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {ArrowUpRight} from 'lucide-react';
import Modal from '../Modal';
import {ApiError} from '../api';
import {projectApi} from './projectApi';
import {projectHref,type ProjectFocus} from './projectNavigation';
import {trendLeadApi,type TrendCaptureTarget,type TrendLead} from './trendLeadApi';
import './trend-project-capture.css';

export default function TrendProjectCapture({target,onClose,onProject}:{target:TrendCaptureTarget;onClose:()=>void;onProject:(target:ProjectFocus|null)=>void}){
 const qc=useQueryClient(),[projectId,setProjectId]=useState(''),[reason,setReason]=useState(''),[paperIds,setPaperIds]=useState<string[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState(''),[conflict,setConflict]=useState(false),[saved,setSaved]=useState<{lead:TrendLead;projectId:string}|null>(null);
 const initialised=useRef(false);
 const projects=useQuery({queryKey:['projects'],queryFn:projectApi.list,staleTime:0});
 const preview=useQuery({queryKey:['project-trend-preview',target],queryFn:()=>trendLeadApi.preview(target),staleTime:Infinity,refetchOnMount:'always',refetchOnWindowFocus:false});
 const snapshot=preview.data?.snapshot,selectedId=projectId||projects.data?.items[0]?.id||'';
 const localPapers=snapshot?.papers.filter(p=>p.local_version!==null&&p.relevant!==false)||[];
 const focusPaper=snapshot?.papers.find(p=>p.id===snapshot.focus_paper_id);
 useEffect(()=>{if(!snapshot||initialised.current)return;initialised.current=true;setPaperIds(target.paperId&&localPapers.some(p=>p.id===target.paperId)?[target.paperId]:[])},[snapshot]);
 async function reload(){setError('');try{const result=await preview.refetch();if(result.error)throw result.error;setPaperIds(old=>old.filter(id=>result.data?.snapshot.papers.some(p=>p.id===id&&p.local_version!==null&&p.relevant!==false)));setConflict(false)}catch(e){setError((e as Error).message)}}
 async function save(){if(!preview.data||!selectedId||reason.trim().length<4||conflict||preview.isFetching)return;setBusy(true);setError('');try{const lead=await trendLeadApi.capture(selectedId,target,preview.data.source_key,reason,paperIds);setSaved({lead,projectId:selectedId});await Promise.all([qc.invalidateQueries({queryKey:['project-trend-leads',selectedId]}),qc.invalidateQueries({queryKey:['project-candidates',selectedId]}),qc.invalidateQueries({queryKey:['paper-projects']}),qc.invalidateQueries({queryKey:['project',selectedId]})])}catch(e){setError((e as Error).message);if(e instanceof ApiError&&e.status===409)setConflict(true)}finally{setBusy(false)}}
 function go(focus:ProjectFocus|null){onClose();onProject(focus)}
 return <Modal title="保存趋势线索" onClose={()=>{if(!busy)onClose()}} className="trend-project-capture"><div className="trend-capture-body" data-source-key={preview.data?.source_key}>
  {saved?<div className="trend-capture-result" role="status"><h3>项目线索已保存</h3><p>记录保留来源快照与原有关注理由。相同来源重复加入会返回已有记录，不覆盖原取舍，也不扩大原来的论文选择。</p><a className="button primary" href={projectHref({id:saved.projectId,trendLeadId:saved.lead.id})} onClick={e=>{if(!e.metaKey&&!e.ctrlKey&&!e.shiftKey&&!e.altKey){e.preventDefault();go({id:saved.projectId,trendLeadId:saved.lead.id})}}}>前往项目处理 <ArrowUpRight size={14}/></a><button className="text-button" onClick={onClose}>继续查看趋势</button></div>:<>
   {preview.isLoading?<p role="status">正在核对趋势来源…</p>:preview.isError?<div role="alert"><p>{preview.error.message}</p><button className="button small" onClick={()=>void reload()}>重载趋势来源</button></div>:snapshot&&<>
    <header className="trend-capture-heading"><span>{focusPaper?'论文线索':'方向线索'}</span><h3>{focusPaper?.title||snapshot.name}</h3><p className="trend-capture-scope">{snapshot.name} · {snapshot.scope.start}—{snapshot.scope.end} · {snapshot.scope.interval==='year'?'按年':'按月'}{snapshot.scope.period?` · 来源周期 ${snapshot.scope.period}`:''}</p></header>
    <p className="trend-capture-note">保存当时的检索口径、统计与样本依据。趋势信号用于提出研究问题；加入线索不代表结论已核实，也不会自动发起分析。</p>
    <details className="trend-capture-source"><summary>核对将保存的来源</summary><p>{snapshot.source} · {snapshot.date_basis}</p><code>{snapshot.query}</code><p>已获取 {snapshot.points.filter(p=>p.count!==null).length}/{snapshot.points.length} 个统计点 · 来源周期样本 {snapshot.signal.sample===undefined?'未获取':`${snapshot.signal.sample} 篇`} · 方向概览创新空间 {snapshot.signal.y??'待核查'}</p>{focusPaper&&<><blockquote>{focusPaper.quote||'该样本没有可展示的引文。'}</blockquote><p>{focusPaper.bottleneck}</p></>}{snapshot.points.some(p=>p.count===null)&&<p>含未获取统计，缺失值会原样保留。</p>}{snapshot.points.some(p=>p.partial)&&<p>含未结束周期，计数不作为完整周期判断。</p>}</details>
   </>}
   {projects.isLoading?<p role="status">正在载入项目…</p>:projects.isError?<div role="alert"><p>{projects.error.message}</p><button className="text-button" onClick={()=>projects.refetch()}>重新载入项目</button></div>:projects.data?.items.length?<form onSubmit={e=>{e.preventDefault();void save()}}>
    <label>目标项目<select aria-label="目标项目" value={selectedId} disabled={busy} onChange={e=>setProjectId(e.target.value)}>{projects.data.items.map(p=><option key={p.id} value={p.id}>{p.title}</option>)}</select></label>
    <label>关注理由<textarea aria-label="关注理由" required minLength={4} maxLength={5000} rows={3} value={reason} disabled={busy} onChange={e=>setReason(e.target.value)} placeholder="这个方向或样本与项目的哪个问题有关？还需核对什么条件？至少 4 字。"/></label>
    {!!localPapers.length&&<fieldset className="trend-capture-papers" disabled={busy||preview.isFetching}><legend>同时加入论文候选 <small>可选，不建立正式证据</small></legend>{localPapers.map(p=><label key={p.id}><input type="checkbox" aria-label={'同时加入论文候选：'+p.title} checked={paperIds.includes(p.id)} onChange={e=>setPaperIds(old=>e.target.checked?[...old,p.id]:old.filter(id=>id!==p.id))}/><span>{p.title}<small>本地 v{p.local_version} · {p.id}</small></span></label>)}</fieldset>}
    {focusPaper?.local_version===null&&<p className="trend-capture-note">此样本尚未进入本地文库。本次只保留趋势出处与判断，不创建论文候选。</p>}
    {error&&<p className="notice error" role="alert">{error}{conflict?'；关注理由与选择已保留，请核对更新后的来源再保存。':''}</p>}
    {conflict&&<button type="button" className="button small" disabled={busy||preview.isFetching} onClick={()=>void reload()}>重载来源并保留输入</button>}
    <div className="trend-capture-actions"><button className="button primary" type="submit" disabled={busy||!preview.data||preview.isFetching||preview.isError||reason.trim().length<4||!selectedId||conflict}>{busy?'正在保存…':'保存项目线索'}</button><button type="button" className="text-button" disabled={busy} onClick={onClose}>取消</button></div>
   </form>:<div className="trend-capture-no-project"><p>先创建研发项目、明确决策问题，再把趋势与论文作为线索收进来。</p><button className="button primary" onClick={()=>go(null)}>前往创建研发项目 <ArrowUpRight size={14}/></button></div>}
  </>}
 </div></Modal>;
}

import {useState} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {Activity,CheckCircle2,LoaderCircle,RefreshCw,Trash2,TriangleAlert} from 'lucide-react';
import {api,date,type Domain,type Job} from '../api';
import MacroProgress from '../MacroProgress';
import CoauthorProgress from '../CoauthorProgress';
import '../job-status.css';

const kindNames:Record<string,string>={ingest:'文献同步',analyze:'全文分析',survey:'综述阅读',test_llm:'连接测试',lesson:'数学讲解',trends:'宏观趋势统计',explore:'论文探索',trend_download:'趋势论文收录与下载'};
const statusNames:Record<string,string>={queued:'排队中',running:'执行中',waiting:'等待恢复',paused:'已暂停',done:'已完成',failed:'失败',cancelled:'已取消'};
const stageNames:Record<string,string>={search:'检索',rank:'重要性筛选',fetch:'下载收录',analyze:'全文分析',statistics:'统计'};
type TaskAction=(fn:()=>Promise<string>)=>Promise<void>;

function JobRow({job:j,domains,busy,run}:{job:Job;domains:Domain[];busy:boolean;run:TaskAction}){
 const scope=domains.filter(d=>d.id===j.payload.domain_id||j.payload.domain_ids?.includes(d.id)).map(d=>d.name).join('、');
 const canPause=['running','queued','waiting','paused'].includes(j.status);
 return <div className="job-row" id={'job-'+j.id}>
  <div className={'job-icon '+j.status}>{j.status==='done'?<CheckCircle2 size={20}/>:j.status==='failed'?<TriangleAlert size={20}/>:<LoaderCircle size={20} className={j.status==='running'?'spin':''}/>}</div>
  <div className="job-main">
   <strong>{kindNames[j.kind]||j.kind}<span>{scope}</span></strong>
   <div className="job-status-line"><span className={'job-status-badge '+j.status}>{statusNames[j.status]||j.status}</span>{j.payload.start&&<span>{j.payload.start} — {j.payload.end}</span>}{j.status==='running'&&<span>{stageNames[j.result?.stage||'']||'处理中'} · {Math.round(j.progress)}%</span>}</div>
   <p>{j.message}</p>
   {j.status==='waiting'&&j.result?.resume_after&&<small className="job-resume">预计恢复：{new Date(j.result.resume_after).toLocaleString('zh-CN')}</small>}
   {j.status==='running'&&<div className="progress"><i style={{width:j.progress+'%'}}/></div>}
  </div>
  <span className="job-date">{date(j.created)}</span>
  {canPause&&<button className="button small" disabled={busy} onClick={()=>run(async()=>{await api(`/jobs/${j.id}/${j.status==='paused'?'resume':'pause'}`,{method:'POST'});return j.status==='paused'?'已恢复任务':'暂停请求已提交，后台将在检查点保存进度'})}>{j.status==='paused'?'继续任务':'暂停并保存'}</button>}
  {j.status==='failed'&&<button className="button small" disabled={busy} onClick={()=>run(async()=>{await api(`/jobs/${j.id}/retry`,{method:'POST'});return '任务已重新排队'})}>重试</button>}
  <button className="icon-button" disabled={busy} aria-label="删除任务" title="移除记录；未完成任务会停止后续执行" onClick={()=>run(async()=>{await api(`/jobs/${j.id}`,{method:'DELETE'});return '任务已移除，已有成果保留'})}><Trash2 size={16}/></button>
 </div>;
}

export default function JobsPage({domains,domain,onNotice}:{domains:Domain[];domain:string;onNotice:(message:string)=>void}){
 const qc=useQueryClient();
 const jobs=useQuery({queryKey:['jobs'],queryFn:()=>api<Job[]>('/jobs'),refetchInterval:5000});
 const control=useQuery({queryKey:['job-control'],queryFn:()=>api<{paused:boolean}>('/jobs/control'),refetchInterval:5000});
 const [busy,setBusy]=useState(false);
 const rows=jobs.data||[];
 async function run(fn:()=>Promise<string>){
  setBusy(true);
  try{
   onNotice(await fn());
   await Promise.all([qc.invalidateQueries({queryKey:['jobs']}),qc.invalidateQueries({queryKey:['job-control']}),qc.invalidateQueries({queryKey:['exploration-latest']})]);
  }catch(error){onNotice((error as Error).message)}finally{setBusy(false)}
 }
 const error=jobs.error||control.error;
 return <>
  <CoauthorProgress/><MacroProgress/>
  {error&&<div className="notice error"><TriangleAlert size={18}/>{(error as Error).message}<button onClick={()=>{void jobs.refetch();void control.refetch()}}>重试</button></div>}
  <section className="panel">
   <div className="panel-title"><div><h2>全部任务记录</h2><p>{control.data?.paused?'后台队列已暂停；项目中明确提交的定向收录可单独运行，其他任务等待恢复':'自动探索每 24 小时运行；失败任务可从检查点继续'}</p></div>
    <div className="job-actions">
     <button className="button small" disabled={busy} onClick={()=>run(async()=>{const r=await api<{duplicates_cancelled:number;completed_cancelled:number}>('/jobs/manage',{method:'POST'});return `已取消 ${r.duplicates_cancelled} 项重复任务、${r.completed_cancelled} 项已完成分析的重复计算`})}>整理重复任务</button>
     <button className="button small" disabled={busy||!control.data} onClick={()=>run(async()=>{const paused=control.data!.paused;await api('/jobs/'+(paused?'resume-all':'pause-all'),{method:'POST'});return paused?'后台队列已恢复':'全部任务已请求暂停，当前请求完成后保存进度'})}>{control.data?.paused?'恢复后台队列':'一键暂停全部'}</button>
     <button className="button small" disabled={busy||!rows.some(j=>j.status==='failed'||j.status==='waiting')} onClick={()=>run(async()=>{const r=await api<{retried:number;skipped:number}>('/jobs/retry-all',{method:'POST'});return `已重新排队 ${r.retried} 项；跳过 ${r.skipped} 项（额度、取消、重复或缺少配置）`})}><RefreshCw size={15} className={busy?'spin':''}/>一键重试</button>
     <span className="tag">{rows.filter(j=>j.status==='running').length} 执行 · {rows.filter(j=>j.status==='queued').length} 排队 · {rows.filter(j=>j.status==='waiting').length} 等待恢复</span>
    </div>
   </div>
   {jobs.isLoading?<div className="loading"><LoaderCircle size={20} className="spin"/> 正在加载任务</div>:rows.length?rows.map(j=><JobRow key={j.id} job={j} domains={domains} busy={busy} run={run}/>):!jobs.error&&<div className="empty"><div className="empty-icon"><Activity size={27}/></div><h3>{domain?'此领域暂无任务':'还没有后台任务'}</h3><p>同步论文或发起分析后，可以在这里查看进度。</p></div>}
  </section>
 </>;
}

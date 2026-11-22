import {useEffect,useState,type FormEvent} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {Check,LoaderCircle,TriangleAlert} from 'lucide-react';
import {api,type ModelBudget,type ModelUsage} from '../api';
import './model-budget.css';

const fields=[{key:'daily_tokens',label:'每日 Token 上限',note:'北京时间零点重新计数。'},{key:'task_tokens',label:'每任务 Token 上限',note:'同一任务的分析、修复等调用合并计数。'},{key:'task_calls',label:'每任务调用上限',note:'包括实际发送给模型的重试请求。'}] as const;
type Values=Record<typeof fields[number]['key'],string>;
const values=(budget:ModelBudget):Values=>({daily_tokens:budget.daily_tokens?.toString()||'',task_tokens:budget.task_tokens?.toString()||'',task_calls:budget.task_calls?.toString()||''});

function BudgetForm({budget,onNotice}:{budget:ModelBudget;onNotice:(message:string)=>void}){
 const qc=useQueryClient();
 const [inputs,setInputs]=useState(()=>values(budget));
 const [dirty,setDirty]=useState(false),[saving,setSaving]=useState(false);
 useEffect(()=>{if(!dirty)setInputs(values(budget))},[budget,dirty]);
 async function submit(event:FormEvent){
  event.preventDefault();
  const body:Partial<Omit<ModelBudget,'timezone'>>={};
  for(const {key,label} of fields){
   const value=inputs[key].trim();
   if(value!==''&&(!Number.isSafeInteger(Number(value))||Number(value)<=0)){onNotice(label+'需填写正整数，留空表示不设上限');return}
   body[key]=value===''?null:Number(value);
  }
  setSaving(true);
  try{
   const updated=await api<ModelBudget>('/model-usage/budget',{method:'PUT',body:JSON.stringify(body)});
   qc.setQueryData(['model-budget'],updated);
   setInputs(values(updated));setDirty(false);
   await qc.invalidateQueries({queryKey:['model-usage']});
   onNotice('模型调用预算已保存');
  }catch(error){onNotice((error as Error).message)}finally{setSaving(false)}
 }
 return <form className="form" onSubmit={submit}>
  <div className="form-grid">{fields.map(({key,label,note})=><label key={key}>{label}<input aria-label={label} type="number" min={1} max={Number.MAX_SAFE_INTEGER} step={1} value={inputs[key]} placeholder="不设上限" disabled={saving} onChange={event=>{setInputs({...inputs,[key]:event.target.value});setDirty(true)}}/><small>{note}留空表示不设上限。</small></label>)}</div>
  <p className="model-budget-note">发送请求前预留输入及输出额度，收到服务商用量后结算。用量无法确认时保留预留额度，避免重复请求超出预算。此处记录 Token 和调用次数。</p>
  <div className="form-actions"><button className="button primary" disabled={saving||!dirty}>{saving?<LoaderCircle size={16} className="spin"/>:<Check size={16}/>}保存调用预算</button></div>
 </form>;
}

export default function ModelBudgetSettings({onNotice}:{onNotice:(message:string)=>void}){
 const budget=useQuery({queryKey:['model-budget'],queryFn:()=>api<ModelBudget>('/model-usage/budget'),refetchOnWindowFocus:false});
 const usage=useQuery({queryKey:['model-usage'],queryFn:()=>api<ModelUsage>('/model-usage'),refetchInterval:15000});
 return <section className="panel model-budget-settings" aria-labelledby="model-budget-title">
  <div className="panel-title"><div><h2 id="model-budget-title">模型调用预算与用量</h2><p>为全文分析、讲解与问答设置统一调用额度；填写后保存生效。</p></div><button className="button small" disabled={usage.isFetching} onClick={()=>usage.refetch()}>刷新用量</button></div>
  {usage.data&&<div className="model-usage-totals" aria-label={'模型调用用量 · '+usage.data.day}><div><span>已报告 Token</span><strong>{usage.data.totals.known_tokens.toLocaleString()}</strong></div><div><span>待确认预留 Token</span><strong>{usage.data.totals.reserved_tokens.toLocaleString()}</strong></div><div><span>已记录请求</span><strong>{usage.data.totals.attempts.toLocaleString()}</strong></div><div><span>用量未知请求</span><strong>{usage.data.totals.unknown_calls.toLocaleString()}</strong></div><small>{usage.data.day} · 北京时间 · 预留量为估计额度，实际用量以服务商报告为准。</small></div>}
  {!!usage.data?.totals.unknown_calls&&<p className="model-budget-note" role="status">存在用量未知的请求，预留额度会继续保留。{budget.data?.daily_tokens!=null?'已设置每日 Token 上限，今天的新模型请求将暂停。':'设置了每任务 Token 上限的相关任务将暂停后续调用。'}请先核对模型服务记录。</p>}
  {budget.error&&<div className="notice error"><TriangleAlert size={18}/>{budget.error.message}<button onClick={()=>budget.refetch()}>重试加载预算</button></div>}
  {usage.error&&<p className="model-budget-note">用量统计暂时无法读取：{usage.error.message}</p>}
  {budget.isLoading?<div className="loading"><LoaderCircle size={20} className="spin"/>正在加载调用预算</div>:budget.data&&<BudgetForm budget={budget.data} onNotice={onNotice}/>}
 </section>;
}

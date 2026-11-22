import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api} from './api';
import './coauthor-progress.css';
type Row={paper_id:string;title:string;route:string;status:string;tokens?:number;error:string;executor?:string};
type Progress={items:Row[];total:number;counts:Record<string,number>;updated_at:number|null;blocked:boolean};
const names:Record<string,string>={queued:'等待处理',extracting:'提取证据', 'evidence-ready':'证据就绪 · 待组织正文',generating:'生成修订稿','awaiting-gpt-review':'待 GPT 复核',failed:'失败 · 已保存',conflict:'版本冲突',published:'已入库'};
export default function CoauthorProgress(){
 const [filter,setFilter]=useState('all');
 const q=useQuery({queryKey:['coauthor-batch'],queryFn:()=>api<Progress>('/coauthor-batch'),refetchInterval:5000});
 if(q.isError)return <section className="panel coauthor-progress"><p role="alert">协作进度暂时无法读取 <button className="text-button" onClick={()=>q.refetch()}>重试</button></p></section>;
 if(!q.data?.total)return null;const d=q.data;
 return <section className="panel coauthor-progress"><header><div><span className="eyebrow">LITERATURE STUDY</span><h2>全文研读 · 协作批次</h2></div><span className="tag">{d.blocked?'提取批次已阻塞':'检查点进度'} · {d.total} 篇</span></header><div className="coauthor-stages">{[['queued','等待处理'],['extracting','证据提取中'],['evidence-ready','证据就绪'],['generating','正文生成中'],['awaiting-gpt-review','待复核'],['published','已入库']].map(([key,label])=><div key={key}><strong>{d.counts[key]||0}</strong><span>{label}</span></div>)}</div><progress aria-label="研读入库进度" max={d.total} value={d.counts.published||0}/><p>已入库 {d.counts.published||0} / {d.total} · 证据就绪和生成草稿不计作完成</p>{d.blocked&&<p role="status" className="notice">证据提取遇到校验失败，批次已停止；已完成的草稿与证据保留。</p>}<details><summary>查看论文进度 · {d.counts.failed||0} 项失败</summary><label>筛选 <select value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">全部</option>{Object.entries(names).map(([key,name])=><option value={key} key={key}>{name} ({d.counts[key]||0})</option>)}</select></label><div className="coauthor-rows">{d.items.filter(r=>filter==='all'||r.status===filter).map(r=><article key={r.paper_id}><div><strong>{r.title}</strong><small>{r.route==='style'?'存量修订':'补充全文'}{r.executor?' · '+r.executor:''}{r.tokens?' · '+r.tokens.toLocaleString()+' token':''}</small>{r.error&&<p>{r.error}</p>}</div><span className={'coauthor-state '+r.status}>{names[r.status]||r.status}</span></article>)}</div></details><small>每 5 秒刷新 · 最近检查点 {d.updated_at?new Date(d.updated_at*1000).toLocaleString('zh-CN'):'—'} · 与自动探索队列分开运行</small></section>
}

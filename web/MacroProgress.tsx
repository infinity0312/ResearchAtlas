import {useQuery} from '@tanstack/react-query';
import {api} from './api';
import './coauthor-progress.css';
const names:Record<string,string>={queued:'待 DeepSeek 处理',generating:'DeepSeek 候选评分', 'awaiting-gpt-review':'待 GPT 逐篇复核',paused:'已暂停',failed:'失败 · 检查点已保存',published:'已发布'};
export default function MacroProgress(){
 const q=useQuery({queryKey:['macro-coauthor'],queryFn:()=>api<{items:{work_id:string;name:string;year:number;status:string;total:number;completed:number;tokens:number}[]}>('/trends/coauthor-progress'),refetchInterval:5000});
 if(!q.data?.items.length)return null;
 return <section className="panel coauthor-progress"><header><div><span className="eyebrow">RESEARCH TRENDS</span><h2>宏观趋势 · 协作分析</h2></div></header><div className="coauthor-rows">{q.data.items.map(r=><article key={r.work_id}><div><strong>{r.name} · {r.year}</strong><small>候选证据 {r.completed} / {r.total} 篇 · {r.tokens.toLocaleString()} token</small></div><span className="coauthor-state">{names[r.status]||r.status}</span></article>)}</div></section>
}

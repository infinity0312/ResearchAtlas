import {useQuery} from '@tanstack/react-query';
import {ArrowUpRight,Layers3} from 'lucide-react';
import {api,date} from './api';
import MathText from './MathText';
type Related={items:{id:string;title:string;published:string;shared_tags:string[];keywords:string[]}[];basis:string;total_candidates:number};
export default function RelatedPapers({id,open}:{id:string;open:(id:string)=>void}){
 const {data,isLoading,error}=useQuery({queryKey:['related',id],queryFn:()=>api<Related>('/paper/related?id='+encodeURIComponent(id))});
 return <section className="related-papers"><div className="related-heading"><Layers3 size={20}/><div><h3>继续探索相关研究</h3><p>{data?.basis||'根据本地文献的共同标签与关键词查找'}</p></div></div>{isLoading?<p role="status">正在查找相关文献…</p>:error?<p role="alert">{error.message}</p>:data?.items.length?<div className="related-list">{data.items.map(p=><button className="related-card" key={p.id} onClick={()=>open(p.id)}><div><span>arXiv:{p.id}</span><span>{date(p.published)}</span></div><h4><MathText text={p.title}/><ArrowUpRight size={16}/></h4><p>{p.shared_tags.length?'共同标签：'+p.shared_tags.slice(0,3).join(' · '):'相近关键词：'+p.keywords.join(' · ')}</p></button>)}</div>:<div className="empty"><h3>暂未找到足够相关的文献</h3><p>继续采集论文、补充方法和问题标签后，这里会更新。</p></div>}</section>
}

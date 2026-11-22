import type {GraphData} from './GraphCanvas';
import {timelineDate} from './paperViewData';
import './graph-research.css';

export default function TimelineIndex({data,year,onYear,onPaper}:{
 data:GraphData;year:string;onYear:(year:string)=>void;onPaper:(id:string)=>void;
}){
 const rows=data.papers.map(p=>({p,d:timelineDate(p)}));
 const chronological=rows.filter(row=>row.d.year);
 const years=[...new Set(chronological.map(row=>row.d.year))].sort().reverse();
 const dated=chronological.filter(row=>!year||row.d.year===year)
  .sort((a,b)=>a.d.date.localeCompare(b.d.date)||a.p.title.localeCompare(b.p.title));
 const approximate=rows.filter(row=>row.d.kind==='year');
 const unplaced=rows.filter(row=>!row.d.year);
 const labels={exact:'',year:'仅知年份',announcement:'公告记录',imported:'导入记录',unknown:'日期待核'};
 return <section className="graph-research" aria-label="按年代浏览论文">
  <div className="graph-research-line">
   <label>定位年份<select aria-label="定位年份" value={year} onChange={e=>onYear(e.target.value)}>
    <option value="">全部年份</option>
    {years.map(y=><option value={y} key={y}>{y} 年 · {chronological.filter(row=>row.d.year===y).length} 篇</option>)}
   </select></label>
   <span>{dated.filter(row=>row.d.kind==='exact').length} 篇可按日定位 · {approximate.length} 篇仅知年份 · {unplaced.length} 篇待核日期</span>
  </div>
  {!!dated.length&&<details className="graph-research-list"><summary>按时间查看论文 · {dated.length} 篇</summary>
   <div className="graph-research-dates">{dated.map(({p,d})=><button className="text-button" key={p.id} onClick={()=>onPaper(p.id)}>
    <time>{d.date}</time>{p.title}{d.kind==='year'?' · 仅知年份':p.date_basis==='submitted'?' · 首次提交':p.date_basis==='published'?' · 发表':''}
   </button>)}</div>
  </details>}
  {!!unplaced.length&&<details className="graph-research-list"><summary>{unplaced.length} 篇缺少有效日期，暂未定位</summary>
   <div className="graph-research-dates">{unplaced.map(({p,d})=><button className="text-button" key={p.id} onClick={()=>onPaper(p.id)}>
    <time>{d.date||'—'}</time>{p.title} · {labels[d.kind]}
   </button>)}</div>
  </details>}
 </section>;
}

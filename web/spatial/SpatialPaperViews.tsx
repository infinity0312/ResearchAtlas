import {useEffect,useMemo,useRef,useState} from 'react';
import type {GraphData} from '../GraphCanvas';
import {temporalBundleRadii} from './temporalDensity';
import {similarityMatrix} from '../paperViewData';
import {useAppearance} from '../ui/Appearance';
import {DataReliefScene,type SpatialDatum} from './DataReliefScene';
import './relief.css';
export default function SpatialPaperViews({data,mode,onPaper,reference=data}:{reference?:GraphData;data:GraphData;mode:'similarity'|'timeline';onPaper:(id:string)=>void}){
 const {reduced}=useAppearance(),host=useRef<HTMLDivElement>(null),scene=useRef<DataReliefScene|null>(null);
 const [chosen,setChosen]=useState<number[]>([]),[names,setNames]=useState(true),[status,setStatus]=useState(''),[indexSearch,setIndexSearch]=useState(''),[compare,setCompare]=useState<number|null>(null);
 const model=useMemo(()=>{const matrix=similarityMatrix(data,mode==='similarity',reference),points:SpatialDatum[]=[],axis:{x:number;y:number;text:string;axis?:string;index?:number}[]=[];
  if(mode==='similarity'){const offset=0,column=0,size=data.papers.length,width=data.papers.length;for(const [i,j,v] of matrix.cells){if(i<column||j<offset||i>=column+width||j>=offset+size)continue;const l=95-Math.sqrt(v)*61;points.push({x:i-column-(width-1)/2,y:(size-1)/2-(j-offset),value:v,color:`hsl(44, ${26+v*18}%, ${l}%)`,label:`${(v*100).toFixed(1)}% 标签相似度\n${data.papers[i].title}\n${data.papers[j].title}`,ids:[i,j]})}for(let i=0;i<width;i++)axis.push({x:i-(width-1)/2,y:(size+1)/2,text:String(column+i+1).padStart(2,'0'),axis:'column',index:column+i});for(let i=0;i<size;i++)axis.push({x:-(width+1)/2,y:(size-1)/2-i,text:String(offset+i+1).padStart(2,'0'),axis:'row',index:offset+i})}
  else{
   const dated=data.papers.map((p,i)=>({p,i,t:Date.parse(p.published||'')})).filter(p=>Number.isFinite(p.t));
   const radii=temporalBundleRadii(dated.map(d=>d.t)),radiusById=new Map(dated.map((d,i)=>[d.p.id,radii[i]]));
   const min=Math.min(...dated.map(d=>d.t)),max=Math.max(...dated.map(d=>d.t)),span=Math.max(1,max-min),tags=new Map(data.tags.map(t=>[t.id,t]));
   const laneOf=(id:string)=>[...(matrix.sets.get(id)||[])].map(t=>tags.get(t)).find(t=>t?.kind==='topic')?.name||'其他研究';
   const lanes=[...new Set(dated.map(d=>laneOf(d.p.id)))];
   const occupied:{x:number;y:number;z:number}[]=[];const ordered=[...dated].sort((a,b)=>a.t-b.t||a.p.id.localeCompare(b.p.id));for(const [index,d] of ordered.entries()){const lane=lanes.indexOf(laneOf(d.p.id));
    const x=max===min?0:(d.t-min)/span*22-11;let best={y:0,z:0},score=-Infinity;for(let c=0;c<40;c++){const phase=lane*.7+index*2.399963+c*2.399963,radius=(radiusById.get(d.p.id)||1.15)*(.72+.28*((index+c*.6180339)%1)),y=Math.cos(phase)*radius,z=Math.sin(phase)*radius;let gap=8;for(const q of occupied){const dx=Math.abs(q.x-x);if(dx<2.4)gap=Math.min(gap,Math.abs(q.y-y)+Math.abs(q.z-z)*.35+dx*.3)}if(gap>score){score=gap;best={y,z}}}occupied.push({x,...best});
    points.push({x,y:best.y,z:best.z,bundleRadius:radiusById.get(d.p.id),value:0,color:['#167f91','#234f8c','#9c6737','#438b9a'][lane%4],shortLabel:d.p.label||d.p.title.slice(0,24),label:(d.p.label||d.p.title)+' · '+d.p.published?.slice(0,10),ids:[d.i]})
   }
   if(dated.length){const steps=min===max?0:4;for(let i=0;i<=steps;i++){const t=min+span*i/Math.max(1,steps);axis.push({x:steps?-11+22*i/steps:0,y:-.6,text:new Date(t).toISOString().slice(0,7)})}}
  }
  const dates=data.papers.map(p=>Date.parse(p.published||'')).filter(Number.isFinite);return {points,axis,timeRange:dates.length?[Math.min(...dates),Math.max(...dates)] as [number,number]:undefined};
 },[data,mode,reference]);
 useEffect(()=>{setChosen([]);setCompare(null);setStatus('');try{scene.current=new DataReliefScene(host.current!,model.points,mode,setChosen,setStatus,reduced,model.axis,model.timeRange);scene.current.setNames(names);if(mode==='similarity'&&data.papers.length>80)scene.current.focusMatrixCell(11,11,data.papers.length)}catch{setStatus('三维渲染不可用，可切换二维视图')}return()=>{scene.current?.dispose();scene.current=null}},[model,mode,reduced]);
 const locate=(index:number)=>{const pair=compare===null?[index,index]:[compare,index];setChosen(pair);scene.current?.focusMatrixCell(pair[0],pair[1],data.papers.length)};
 const selected=chosen.filter(index=>!!data.papers[index]);
 return <div className="paper-view spatial-paper-view" data-view={mode} data-total-papers={data.papers.length} data-matrix-cells={mode==='similarity'?model.points.length:undefined}>
 <div className="relief-toolbar"><button className="button small" aria-label="放大数据空间" onClick={()=>scene.current?.zoom(.8)}>放大</button><button className="button small" aria-label="缩小数据空间" onClick={()=>scene.current?.zoom(1.25)}>缩小</button><button className="button small" onClick={()=>scene.current?.reset()}>全览</button>{mode==='similarity'&&<button className="button small" onClick={()=>scene.current?.focusMatrixCell(chosen[0]??Math.min(11,data.papers.length-1),chosen[1]??chosen[0]??Math.min(11,data.papers.length-1),data.papers.length)}>可读窗口</button>}{mode==='timeline'&&<button className="button small" aria-pressed={names} onClick={()=>{setNames(!names);scene.current?.setNames(!names)}}>论文简名</button>}{status&&<span role="status">{status}</span>}</div>
 {mode==='similarity'&&<div className="relief-scale"><span>0%</span><i/><span>100% 标签相似度</span></div>}
 {!model.points.length&&<p className="notice">{mode==='similarity'?'当前范围内没有可比较的分类标签。':'当前论文缺少有效发表日期。'}</p>}
 {mode==='similarity'&&<div className="pv-matrix-navigation"><span>已加载 {data.papers.length} 篇 · 初始显示可读窗口，全部比较数据保留；可切全览或通过索引定位。</span><input aria-label="查找并定位相似矩阵文献" placeholder="标题或简名" value={indexSearch} onChange={event=>setIndexSearch(event.target.value)}/></div>}
 <div className={mode==='similarity'?'pv-spatial-workspace':''}><div className="paper-view-chart relief-host" ref={host} role="img" aria-label={mode==='similarity'?'三维论文相似度矩阵':'三维论文时间纤维图'}/>{mode==='similarity'&&<aside className="pv-index"><div className="pv-index-heading">论文索引 · 点击定位</div><div className="pv-index-list">{data.papers.map((paper,index)=>({paper,index})).filter(({paper})=>(paper.title+' '+paper.label).toLowerCase().includes(indexSearch.toLowerCase())).map(({paper,index})=><button key={paper.id} className={selected.includes(index)?'active':''} onClick={()=>locate(index)}><span>{index+1}</span><div><strong>{paper.label||paper.title}</strong><small>{paper.title}</small></div></button>)}</div></aside>}</div>
 <div className="relief-inspector" hidden={!selected.length}>{mode==='similarity'&&selected.length>0&&<div className="pv-comparison-summary"><p>{model.points.find(point=>point.ids[0]===selected[0]&&point.ids[1]===(selected[1]??selected[0]))?`标签相似度 ${(model.points.find(point=>point.ids[0]===selected[0]&&point.ids[1]===(selected[1]??selected[0]))!.value*100).toFixed(1)}%`:'缺少分类标签，无法计算相似度；仍可阅读文献。'}</p><button className="text-button" onClick={()=>setCompare(compare===null?selected[0]:null)}>{compare===null?'以此文献对照另一篇':'取消对照选择'}</button></div>}{[...new Set(selected)].map(i=><button className="relief-paper" key={i} onClick={()=>onPaper(data.papers[i].id)}><small>{data.papers[i].published?.slice(0,10)}</small><strong>{data.papers[i].title}</strong><span>阅读 ↗</span></button>)}</div></div>
}

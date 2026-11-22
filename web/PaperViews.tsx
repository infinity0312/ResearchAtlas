import {industrialChart,industrialHeatmap,industrialSeries} from './ui/industrial/colors';
import MatrixRange from './MatrixRange';
import {useChartSurface} from './ui/useChartSurface';
import {useAppearance} from './ui/Appearance';
import {lazy,Suspense,useEffect,useMemo,useRef,useState} from 'react';
const SpatialPaperViews=lazy(()=>import('./spatial/SpatialPaperViews'));
import * as echarts from 'echarts/core';
import {HeatmapChart,ScatterChart} from 'echarts/charts';
import {GridComponent,TooltipComponent,VisualMapComponent,DataZoomComponent} from 'echarts/components';
import {LabelLayout} from 'echarts/features';
import {CanvasRenderer} from 'echarts/renderers';
import type {GraphData} from './GraphCanvas';
import './paper-views.css';
import {closestByTags,similarityMatrix,timelineDate} from './paperViewData';
import TimelineIndex from './TimelineIndex';
echarts.use([LabelLayout,HeatmapChart,ScatterChart,GridComponent,TooltipComponent,VisualMapComponent,DataZoomComponent,CanvasRenderer]);
const classicPalette=['#397d72','#6483bb','#ab8543','#9a70ae','#bc6877','#4a97a5'];
function FlatPaperViews({data,mode,onPaper,reference=data}:{reference?:GraphData;data:GraphData;mode:'similarity'|'timeline';onPaper:(id:string)=>void}){
 const {appearance,reduced}=useAppearance();
 const graphite=appearance.edition==='industrial';
 const palette=graphite?industrialSeries:appearance.edition==='prism'?['#61876a','#80a187','#b4ad7e','#7c9995','#96a77c','#8696a0']:classicPalette;
 const [pair,setPair]=useState<number[]|null>(null),[selected,setSelected]=useState<string|null>(null),[indexSearch,setIndexSearch]=useState(''),[compare,setCompare]=useState<number|null>(null);
 const {ref,instance:chart}=useChartSurface(e=>{if(mode==='similarity')setPair([e.value[0],e.value[1]]);else if(e.data?.paperId)setSelected(e.data.paperId)});
 const model=useMemo(()=>similarityMatrix(data,mode==='similarity',reference),[data,mode,reference]);

 useEffect(()=>{setPair(null);setCompare(null);const n=data.papers.length,labels=data.papers.map((p,i)=>`${String(i+1).padStart(2,'0')} ${p.label||p.title.slice(0,12)}`);
 if(mode==='similarity')chart.current?.setOption({animation:false,grid:{left:42,right:28,top:30,bottom:72},tooltip:{renderMode:'richText',formatter:(e:any)=>{const [i,j,v]=e.value;return `${data.papers[i].title}\n${data.papers[j].title}\n分类标签相似度 ${(v*100).toFixed(1)}%`}},xAxis:{type:'category',data:labels.map((_,i)=>String(i+1).padStart(2,'0')),position:'top',axisTick:{show:false},axisLine:{show:false},axisLabel:{fontSize:10,color:graphite?industrialChart.muted:'#82918c',interval:'auto'}},yAxis:{type:'category',data:labels.map((_,i)=>String(i+1).padStart(2,'0')),inverse:true,axisTick:{show:false},axisLine:{show:false},axisLabel:{fontSize:10,color:graphite?industrialChart.muted:'#82918c',interval:'auto'}},visualMap:{min:0,max:1,orient:'horizontal',left:'center',bottom:2,itemHeight:130,itemWidth:7,textStyle:{color:graphite?industrialChart.muted:'#7d8d87',fontSize:10},calculable:false,inRange:{color:graphite?industrialHeatmap:appearance.edition==='prism'?['#f4f8ed','#d9e8cf','#b0c8a2','#83a17b','#4d7054']:['#f3f5f1','#d4e1cc','#8fbba5','#4b9386','#245c59']},text:['100%','0%']},dataZoom:[{type:'inside',xAxisIndex:0,filterMode:'filter',minValueSpan:2,startValue:0,endValue:Math.min(n-1,23)},{type:'inside',yAxisIndex:0,filterMode:'filter',minValueSpan:2,startValue:0,endValue:Math.min(n-1,23)},...(n>24?[{type:'slider',xAxisIndex:0,bottom:30,height:12,moveHandleSize:0,showDetail:false,showDataShadow:false,borderColor:'transparent',backgroundColor:graphite?industrialChart.grid:'#eff3f0',fillerColor:graphite?industrialChart.line:'#cbdcd3',handleStyle:{color:graphite?industrialChart.accent:'#729589',borderColor:'#fff'},startValue:0,endValue:Math.min(n-1,23)},{type:'slider',yAxisIndex:0,right:4,width:12,moveHandleSize:0,showDetail:false,showDataShadow:false,borderColor:'transparent',backgroundColor:graphite?industrialChart.grid:'#eff3f0',fillerColor:graphite?industrialChart.line:'#cbdcd3',handleStyle:{color:graphite?industrialChart.accent:'#729589',borderColor:'#fff'},startValue:0,endValue:Math.min(n-1,23)}]:[])],series:[{type:'heatmap',data:model.cells,progressive:5000,itemStyle:{borderWidth:n>80?0:1,borderColor:'#fff'},emphasis:{itemStyle:{borderColor:graphite?industrialChart.ink:'#355e51',borderWidth:2}}}]},true);
 else{
 const tags=new Map(data.tags.map(t=>[t.id,t]));const dated=data.papers.map((p,i)=>{const ts=[...(model.sets.get(p.id)||[])].map(id=>tags.get(id)).filter(Boolean);const lane=ts.find(t=>t!.kind==='topic')?.name||ts.find(t=>t!.kind==='method')?.name||'尚未分类';return {p,i,lane,date:Date.parse(p.published||'')}}).filter(x=>Number.isFinite(x.date));
 const lanes=[...new Set(dated.map(d=>d.lane))].sort();
 // Keep exact publication dates; dodge only vertically when nearby dots collide.
 const offsets=new Map<string,number>(),last=new Map<string,number[]>();
 const dates=dated.map(d=>d.date),span=Math.max(1,Math.max(...dates)-Math.min(...dates));
 const distance=span*16/Math.max(180,(ref.current?.clientWidth||800)-170);
 for(const d of [...dated].sort((a,b)=>a.date-b.date)){
  const slots=last.get(d.lane)||Array(7).fill(-Infinity);let slot=slots.findIndex(v=>d.date-v>distance);
  if(slot<0)slot=slots.indexOf(Math.min(...slots));slots[slot]=d.date;last.set(d.lane,slots);
  offsets.set(d.p.id,[0,.13,-.13,.26,-.26,.39,-.39][slot]);
 }
 chart.current?.setOption({animation:!reduced,animationDuration:220,grid:{left:125,right:45,top:42,bottom:78},tooltip:{renderMode:'richText',formatter:(e:any)=>`${e.data.title}\n${e.data.dateLabel} · ${e.data.lane}\n点击选中论文`},xAxis:{type:'time',boundaryGap:['5%','9%'],axisLine:{onZero:false,lineStyle:{color:graphite?industrialChart.line:'#a6b7ae'}},name:'已知的提交或发表日期',nameLocation:'middle',nameGap:34,splitLine:{show:true,lineStyle:{color:graphite?industrialChart.grid:'#edf1ee',type:'dashed'}},axisLabel:{hideOverlap:true,color:graphite?industrialChart.muted:'#7d8d87',fontSize:11}},yAxis:{type:'value',min:-1,max:Math.max(1,lanes.length),interval:1,axisLabel:{formatter:(v:number)=>lanes[v]||'',width:110,overflow:'truncate',fontSize:11,color:graphite?industrialChart.muted:'#566d63',margin:16},splitArea:{show:true,areaStyle:{color:['#fafbf9','#ffffff']}},splitLine:{show:false},axisTick:{show:false}},dataZoom:[{type:'slider',xAxisIndex:0,bottom:10,height:22,moveHandleSize:0,showDetail:false,borderColor:'transparent',backgroundColor:graphite?industrialChart.grid:'#f1f4f1',fillerColor:graphite?industrialChart.fill:'#cbdcd366',dataBackground:{lineStyle:{color:graphite?industrialChart.line:'#8fa99b'},areaStyle:{color:graphite?industrialChart.line:'#d8e4dc'}},handleStyle:{color:graphite?industrialChart.accent:'#658e7e',borderColor:'#fff'},textStyle:{color:graphite?industrialChart.muted:'#698174'}},{type:'inside',xAxisIndex:0,filterMode:'none',zoomOnMouseWheel:'ctrl'},...(lanes.length>12?[{type:'slider',yAxisIndex:0,right:0,width:14,start:0,end:12/lanes.length*100}]:[])],series:[{type:'scatter',labelLayout:{hideOverlap:true,moveOverlap:'shiftY'},symbolSize:10,data:dated.map(d=>{const offset=offsets.get(d.p.id)||0;return {value:[d.date,lanes.indexOf(d.lane)+offset],paperId:d.p.id,title:d.p.title,dateLabel:d.p.published?.slice(0,10),lane:d.lane,itemStyle:{color:palette[lanes.indexOf(d.lane)%palette.length]},label:{show:dated.length<=65,formatter:d.p.label||'',position:d.date>Math.max(...dates)-span*.1?'left':'right',width:100,overflow:'truncate',distance:7,color:palette[lanes.indexOf(d.lane)%palette.length],fontSize:11,fontWeight:500,backgroundColor:'#ffffffcc',padding:[3,4],borderRadius:3}}}),itemStyle:{borderWidth:2,borderColor:'#fff',opacity:.95,shadowBlur:5,shadowColor:graphite?industrialChart.grid:'#315d4420'},emphasis:{scale:1.4,label:{show:true,position:'top',color:graphite?industrialChart.ink:'#36594e'}}}]},true);
 }
 },[data,mode,model,onPaper,appearance.edition,reduced]);
 const locate=(index:number,anchor?:number)=>{const column=anchor??compare??index,row=index;for(const axis of [0,1]){const target=axis===0?column:row,start=Math.max(0,Math.min(target-11,data.papers.length-24)),end=Math.min(data.papers.length-1,start+23);chart.current?.dispatchAction({type:'dataZoom',dataZoomIndex:axis,startValue:start,endValue:end})}setPair([column,row]);chart.current?.dispatchAction({type:'downplay'});const cell=model.cells.findIndex(c=>c[0]===column&&c[1]===row);if(cell>=0)chart.current?.dispatchAction({type:'highlight',seriesIndex:0,dataIndex:cell})};
 const chosen=pair?pair.map(i=>data.papers[i]).filter(Boolean):[];const common=pair?data.tags.filter(t=>model.sets.get(chosen[0]?.id)?.has(t.id)&&model.sets.get(chosen[1]?.id)?.has(t.id)):[];
 const selectedCell=pair&&model.cells.find(([i,j])=>i===pair[0]&&j===pair[1]);
 const neighbors=pair?closestByTags(model.cells,pair[0]):[];
 const shared=new Set(common.map(t=>t.id));
 const uniqueTags=(id:string)=>data.tags.filter(t=>!shared.has(t.id)&&model.sets.get(id)?.has(t.id)).map(t=>t.name).join(' · ')||'无';
 const focused=data.papers.find(p=>p.id===selected);
 return <div className="paper-view" data-view={mode} data-total-papers={data.papers.length} data-matrix-cells={mode==='similarity'?model.cells.length:undefined}>

 {mode==='similarity'&&<div className="pv-matrix-navigation"><span>当前加载 {data.papers.length} 篇 · 初始窗口最多24×24，缩放查看其余；没有移除比较数据。</span><button className="button small" onClick={()=>{for(const axis of [0,1])chart.current?.dispatchAction({type:'dataZoom',dataZoomIndex:axis,start:0,end:100})}}>全览矩阵</button><button className="button small" onClick={()=>locate(pair?.[0]||0)}>可读窗口</button></div>}
 {mode==='similarity'&&<div className="graph-research">
  <p>有分类标签 {data.papers.filter(p=>(model.sets.get(p.id)?.size||0)>0).length}/{data.papers.length} 篇 · 以当前筛选的标签和文献计算</p>
  {pair&&chosen[0]&&<div className="graph-research-result">
   <strong>{chosen[0].label||chosen[0].title}的分类近邻</strong>
   {neighbors.length?<div className="graph-research-similar">{neighbors.map(([i,j,value])=><button key={data.papers[j].id} className="text-button" onClick={()=>locate(j,i)}>
    {data.papers[j].title}<span>{(value*100).toFixed(1)}% · 对照标签</span>
   </button>)}</div>:<p className="graph-research-note">当前范围内暂无共享标签的其他论文。</p>}
  </div>}
 </div>}
 {mode==='similarity'&&<div className="paper-view-detail">{pair&&chosen.length===2?<><span className="pv-eyebrow">{pair[0]===pair[1]?'SELECTED PAPER':'PAIR COMPARISON'}</span><div className="paper-view-pair">{chosen.filter((p,i)=>i===0||p.id!==chosen[0].id).map(p=><button key={p.id} onClick={()=>onPaper(p.id)}>{p.title} <span>阅读 ↗</span></button>)}</div><p>{!selectedCell?'缺少分类标签，无法计算相似度；仍可阅读文献。':pair[0]===pair[1]?'已选定比较起点，请选另一篇。':`标签相似度 ${(selectedCell[2]*100).toFixed(1)}%`}</p><button className="text-button" onClick={()=>setCompare(compare===null?pair[0]:null)}>{compare===null?'以此文献对照另一篇':'取消对照选择'}</button>{pair[0]!==pair[1]&&<>
  <p>共享方法：{common.filter(t=>t.kind==='method').map(t=>t.name).join(' · ')||'无'}</p>
  <p>其他共享分类：{common.filter(t=>t.kind!=='method').map(t=>t.name).join(' · ')||'无'}</p>
  {chosen.map(p=><p key={p.id}>{p.label||p.title}独有：{uniqueTags(p.id)}</p>)}
 </>}</>:<p>点击色块查看两篇论文的共享分类，点击索引编号定位论文。</p>}<small>加权 Jaccard · 高频分类降权 · 浅色至深色表示 0–100% · 无标签论文留空</small></div>}
 <div className="pv-workspace">
 <div className="pv-plot">{mode==='timeline'&&<div className="pv-range"><span>时间窗口</span><button onClick={()=>chart.current?.dispatchAction({type:'dataZoom',dataZoomIndex:0,start:0,end:100})}>全部历史</button><button onClick={()=>{const dates=data.papers.map(p=>Date.parse(p.published||'')).filter(Number.isFinite);if(!dates.length)return;const end=Math.max(...dates);chart.current?.dispatchAction({type:'dataZoom',dataZoomIndex:0,startValue:end-10*365.25*86400000,endValue:end})}}>最近十年</button></div>}<div ref={ref} className="paper-view-chart" role="img" aria-label={mode==='similarity'?'论文分类相似度矩阵':'论文时间轴散点图'}/></div>
 {mode==='similarity'&&<aside className="pv-index"><div className="pv-index-heading">论文索引 <span>点击编号定位</span></div><input aria-label="查找并定位相似矩阵文献" placeholder="标题或简名" value={indexSearch} onChange={event=>setIndexSearch(event.target.value)}/><div className="pv-index-list">{data.papers.map((p,i)=>({p,i})).filter(({p})=>(p.title+' '+p.label).toLowerCase().includes(indexSearch.toLowerCase())).map(({p,i})=><button key={p.id} className={pair?.includes(i)?'active':''} onClick={()=>locate(i)}><span>{String(i+1).padStart(2,'0')}</span><div><strong>{p.label||p.title}</strong><small>{p.title}</small></div></button>)}</div></aside>}
 </div>
 {mode==='timeline'?<div className="paper-view-detail">{focused?<div className="pv-selected"><time>{focused.published?.slice(0,10)}</time><strong>{focused.title}</strong><button className="button small" onClick={()=>onPaper(focused.id)}>阅读论文 ↗</button></div>:<p>悬停查看完整标题，点击圆点选择论文；拖动底部时间窗聚焦一个时期。</p>}</div>:null}
 </div>
}

export default function PaperViews(props:{data:GraphData;mode:'similarity'|'timeline';onPaper:(id:string)=>void;flat?:boolean}){
 const {appearance}=useAppearance();const [selected,setSelected]=useState<string[]|null>(null);
 const [year,setYear]=useState('');
 const activeYear=year&&props.data.papers.some(p=>timelineDate(p).year===year)?year:'';
 const outside=selected?.filter(id=>!props.data.papers.some(p=>p.id===id))||[];
 const data=useMemo(()=>{if(props.mode==='timeline'){
  const papers=props.data.papers.filter(p=>{const d=timelineDate(p);return d.kind==='exact'&&(!activeYear||d.year===activeYear)});
  return {...props.data,papers};
 }if(selected===null)return props.data;const ids=new Set(selected);return {...props.data,papers:props.data.papers.filter(p=>ids.has(p.id)),links:props.data.links.filter(l=>ids.has(l.paper_id))}},[props.data,props.mode,selected,activeYear]);
 return <>{props.mode==='timeline'&&<TimelineIndex data={props.data} year={activeYear} onYear={setYear} onPaper={props.onPaper}/>}{props.mode==='similarity'&&outside.length>0&&<div className="notice" role="status">比较范围中 {outside.length} 篇不在当前领域或时间筛选内；当前可比较 {data.papers.length} / {props.data.papers.length} 篇。<button className="text-button" onClick={()=>setSelected(null)}>恢复当前筛选的全部论文</button></div>}{props.mode==='similarity'&&<MatrixRange key={props.data.papers.map(p=>p.id).join('|')} papers={props.data.papers} selected={selected} onApply={setSelected}/>} {!data.papers.length?<div className="empty">{props.mode==='timeline'?'当前范围暂无可按日定位的论文':'请选择需要比较的论文'}</div>:appearance.edition==='prism'&&appearance.effects==='auto'&&!props.flat?<Suspense fallback={<div className="empty">正在构建数据空间…</div>}><SpatialPaperViews {...props} data={data} reference={props.data}/></Suspense>:<FlatPaperViews {...props} data={data} reference={props.data}/>}</>;
}

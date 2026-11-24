import {industrialChart} from './ui/industrial/colors';
import {useChartSurface} from './ui/useChartSurface';
import {useAppearance} from './ui/Appearance';
import {useEffect,useRef} from 'react';
import * as echarts from 'echarts/core';
import {LineChart,BarChart} from 'echarts/charts';
import {GridComponent,TooltipComponent} from 'echarts/components';
import {CanvasRenderer} from 'echarts/renderers';
echarts.use([LineChart,BarChart,GridComponent,TooltipComponent,CanvasRenderer]);
export default function Chart({data,type='line',onSelect}:{data:{name:string;value:number}[];type?:'line'|'bar';onSelect?:(name:string)=>void}){
 const {appearance,reduced}=useAppearance();
 const graphite=appearance.edition==='industrial';
 const {ref,instance}=useChartSurface(p=>onSelect?.(p.name));
 useEffect(()=>{instance.current?.setOption({animation:!reduced,animationDuration:350,textStyle:{fontFamily:'Segoe UI, Microsoft YaHei, sans-serif'},grid:{left:type==='bar'?105:42,right:18,top:18,bottom:30},tooltip:{trigger:'axis',renderMode:'richText',backgroundColor:'#fff',borderColor:graphite?industrialChart.line:'#e8e8e8'},xAxis:type==='line'?{type:'category',boundaryGap:false,data:data.map(x=>x.name),axisLine:{show:false},axisTick:{show:false},axisLabel:{color:graphite?industrialChart.muted:'#8d8d8d',fontSize:12}}:{type:'value',minInterval:1,axisLabel:{color:graphite?industrialChart.muted:'#8d8d8d'},splitLine:{lineStyle:{color:graphite?industrialChart.grid:'#f0f0f0'}}},yAxis:type==='line'?{type:'value',minInterval:1,axisLabel:{color:graphite?industrialChart.muted:'#8d8d8d'},splitLine:{lineStyle:{color:graphite?industrialChart.grid:'#f0f0f0'}}}:{type:'category',inverse:true,data:data.map(x=>x.name),axisLine:{show:false},axisTick:{show:false},axisLabel:{color:graphite?industrialChart.ink:'#5f5f5f',fontSize:12,width:90,overflow:'truncate'}},series:[{type:type==='line'?'line':'bar',data:data.map(x=>x.value),smooth:.25,symbolSize:6,showSymbol:data.length<12,itemStyle:{color:graphite?industrialChart.accent:appearance.edition==='prism'?'#979797':'#757575',borderRadius:[0,4,4,0]},lineStyle:{width:2.5},barMaxWidth:16,areaStyle:type==='line'?{color:new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:graphite?industrialChart.accent+'30':appearance.edition==='prism'?'rgba(153,152,149,.19)':'rgba(118,117,114,.19)'},{offset:1,color:graphite?industrialChart.accent+'00':appearance.edition==='prism'?'rgba(153,152,149,0)':'rgba(118,117,114,0)'}])}:undefined}]});},[data,type,onSelect,appearance.edition,reduced]);
 return <div className="chart" ref={ref} role="img" aria-label={type==='line'?'论文新增趋势图':'研究分类分布图'}/>;
}

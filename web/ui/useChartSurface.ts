import {useEffect,useRef} from 'react';
import * as echarts from 'echarts/core';
/** Single owner for chart lifecycle, resize scheduling and current event callbacks. */
export function useChartSurface(onClick?:(event:any)=>void){const ref=useRef<HTMLDivElement>(null),instance=useRef<echarts.ECharts|null>(null),click=useRef(onClick);click.current=onClick;
 useEffect(()=>{const el=ref.current!;const chart=echarts.init(el);instance.current=chart;chart.on('click',event=>click.current?.(event));let frame=0;
 const observer=new ResizeObserver(()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{if(!chart.isDisposed())chart.resize()})});observer.observe(el);
 return()=>{observer.disconnect();cancelAnimationFrame(frame);instance.current=null;chart.dispose()};
 },[]);return {ref,instance};
}

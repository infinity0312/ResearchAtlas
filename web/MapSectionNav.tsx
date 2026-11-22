import {useEffect,useState} from 'react';
const sections=[['map-taxonomy','分类目录'],['map-relations','文献联系'],['map-methods','方法交叉']] as const;
export default function MapSectionNav(){
 const [active,setActive]=useState<string>('map-taxonomy');
 useEffect(()=>{let frame=0;const update=()=>{frame=0;const passed=sections.filter(([id])=>{const el=document.getElementById(id);return el&&el.getBoundingClientRect().top<=70});setActive(passed.at(-1)?.[0]||'map-taxonomy')};const schedule=()=>{if(!frame)frame=requestAnimationFrame(update)};window.addEventListener('scroll',schedule,{passive:true});window.addEventListener('resize',schedule);schedule();return()=>{window.removeEventListener('scroll',schedule);window.removeEventListener('resize',schedule);cancelAnimationFrame(frame)}},[]);
 return <nav className="map-section-nav" aria-label="地图章节">{sections.map(([id,label])=><button key={id} aria-current={active===id?'location':undefined} onClick={()=>document.getElementById(id)?.scrollIntoView({block:'start',behavior:'auto'})}>{label}</button>)}<span>选择对象，再展开依据</span></nav>;
}

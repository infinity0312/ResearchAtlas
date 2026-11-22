import {useEffect,useRef,useState} from 'react';
import {useAppearance} from './Appearance';
import './research-depth.css';

/** Small, reversible depth cues. Reading text and controls never move with them. */
export default function ResearchDepth({compact=false}:{compact?:boolean}){
 const ref=useRef<HTMLDivElement>(null),{appearance,reduced}=useAppearance();
 const [enabled,setEnabled]=useState(true);
 const moving=enabled&&!reduced&&appearance.effects!=='off';
 useEffect(()=>{
  const el=ref.current;if(!el)return;
  if(!moving){el.style.setProperty('--research-depth','0');return}
  let visible=true,frame=0;
  const update=()=>{frame=0;if(!visible)return;const r=el.getBoundingClientRect();el.style.setProperty('--research-depth',String(Math.max(-8,Math.min(8,(innerHeight*.25-r.top)*.035))))};
  const schedule=()=>{if(!frame&&visible)frame=requestAnimationFrame(update)};
  const observer=new IntersectionObserver(([entry])=>{visible=entry.isIntersecting;if(visible)schedule()});observer.observe(el);
  window.addEventListener('scroll',schedule,{passive:true});window.addEventListener('resize',schedule);schedule();
  return()=>{observer.disconnect();window.removeEventListener('scroll',schedule);window.removeEventListener('resize',schedule);cancelAnimationFrame(frame)};
 },[moving]);
 return <div className={'research-depth'+(compact?' compact':'')} ref={ref} data-motion={moving?'enabled':'still'}>
  <div className="research-depth-art" aria-hidden="true"><span className="research-plane back"/><span className="research-plane middle"/><span className="research-plane front"><i/><i/><i/></span></div>
  {!compact&&<label className="research-depth-toggle"><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)}/>空间层次{!moving&&enabled&&<small>静态</small>}</label>}
 </div>;
}

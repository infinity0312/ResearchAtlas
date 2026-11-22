import {useEditionSwatch} from './ui/industrial/colors';
import {useEffect,useRef,useState} from 'react';
import {ChevronDown,Check} from 'lucide-react';
import type {Domain} from './api';
export default function DomainMultiSelect({domains,selected,onChange}:{domains:Domain[];selected:string[];onChange:(ids:string[])=>void}){
 const swatch=useEditionSwatch();
 const [open,setOpen]=useState(false),ref=useRef<HTMLDivElement>(null);
 useEffect(()=>{const close=(e:PointerEvent)=>{if(!ref.current?.contains(e.target as Node))setOpen(false)};document.addEventListener('pointerdown',close);return()=>document.removeEventListener('pointerdown',close)},[]);
 return <div className="domain-multi" ref={ref} onKeyDown={e=>{if(e.key==='Escape')setOpen(false)}}><button className="domain-multi-trigger" aria-label="选择研究领域（多选）" aria-expanded={open} onClick={()=>setOpen(!open)}><span>{selected.length?domains.filter(d=>selected.includes(d.id)).map(d=>d.name).join('、'):'全部研究领域'}</span><ChevronDown size={15}/></button>{open&&<div className="domain-multi-menu" role="group" aria-label="研究领域多选"><div className="domain-multi-header">领域并集 · 可多选<button className="text-button" onClick={()=>onChange([])}>显示全部</button></div>{domains.map(d=><label key={d.id}><input type="checkbox" checked={selected.includes(d.id)} onChange={()=>onChange(selected.includes(d.id)?selected.filter(id=>id!==d.id):[...selected,d.id])}/><i style={{background:swatch(d.color)}}/><span>{d.name}</span>{selected.includes(d.id)&&<Check size={14}/>}</label>)}</div>}</div>
}

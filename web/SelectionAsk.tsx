import {useEffect,useState,type RefObject} from 'react';
import {MessageSquare,Highlighter} from 'lucide-react';
import './selection-ask.css';
export type SelectedPassage={text:string;page:number;token:number};
export default function SelectionAsk({root,onAsk}:{root:RefObject<HTMLDivElement|null>;onAsk:(p:SelectedPassage)=>void}){
 const [choice,setChoice]=useState<{text:string;page:number;x:number;y:number;sheet:Element|null;rects:{x:number;y:number;w:number;h:number}[]}|null>(null);
 useEffect(()=>{
  const check=()=>{
   const s=window.getSelection();if(!s||s.isCollapsed||!s.rangeCount){setChoice(null);return}
   const r=s.getRangeAt(0),host=root.current;
   if(!host?.contains(r.startContainer)||!host.contains(r.endContainer)){setChoice(null);return}
   const el=r.startContainer.nodeType===1?r.startContainer as Element:r.startContainer.parentElement;
   if(el?.closest('input,textarea,.paper-chat,.reader-tags,.detail-actions,.pdf-highlights,.pdf-mark-actions')){setChoice(null);return}
   const fragment=r.cloneContents();fragment.querySelectorAll('.katex').forEach(k=>{const tex=k.querySelector('annotation[encoding="application/x-tex"]')?.textContent;if(tex)k.replaceWith(document.createTextNode('$'+tex+'$'))});
   const text=(fragment.textContent||s.toString()).trim();
   if(text.length<2||text.length>8000){setChoice(null);return}
   const box=r.getBoundingClientRect(),sheet=el?.closest('[data-pdf-page]')||null,bounds=sheet?.getBoundingClientRect();
   const end=r.endContainer.nodeType===1?r.endContainer as Element:r.endContainer.parentElement;
   const rects=bounds&&end?.closest('[data-pdf-page]')===sheet?Array.from(r.getClientRects()).filter(b=>b.width>0&&b.height>0&&b.width<bounds.width*.99).map(b=>{const left=Math.max(b.left,bounds.left),top=Math.max(b.top,bounds.top),right=Math.min(b.right,bounds.right),bottom=Math.min(b.bottom,bounds.bottom);return {x:(left-bounds.left)/bounds.width,y:(top-bounds.top)/bounds.height,w:(right-left)/bounds.width,h:(bottom-top)/bounds.height}}).filter(b=>b.w>0&&b.h>0):[];
   setChoice({text,sheet,rects,page:Number(el?.closest('[data-pdf-page]')?.getAttribute('data-pdf-page')||0),x:Math.max(12,Math.min(window.innerWidth-260,box.left)),y:Math.max(12,Math.min(window.innerHeight-54,box.bottom+8))});
  };
  const dismiss=()=>setChoice(null);const escape=(e:KeyboardEvent)=>{if(e.key==='Escape')dismiss();else if(e.shiftKey)check()};
  document.addEventListener('pointerup',check);document.addEventListener('keyup',escape);document.addEventListener('scroll',dismiss,true);window.addEventListener('resize',dismiss);
  return()=>{document.removeEventListener('pointerup',check);document.removeEventListener('keyup',escape);document.removeEventListener('scroll',dismiss,true);window.removeEventListener('resize',dismiss)};
 },[root]);
 return choice&&<div className="selection-ask" role="toolbar" aria-label="选中文本操作" style={{left:choice.x,top:choice.y}} onPointerDown={e=>e.preventDefault()}><button onClick={()=>{onAsk({text:choice.text,page:choice.page,token:Date.now()});setChoice(null);window.getSelection()?.removeAllRanges()}}><MessageSquare size={15}/>就此提问</button>{choice.sheet&&choice.rects.length>0&&<button onClick={()=>{choice.sheet?.dispatchEvent(new CustomEvent('atlas-highlight',{bubbles:true,detail:{quote:choice.text,page:choice.page,rects:choice.rects}}));setChoice(null);window.getSelection()?.removeAllRanges()}}><Highlighter size={15}/>高亮标注</button>}</div>;
}

import {useEffect,useRef} from 'react';
import {useAppearance} from '../Appearance';

export default function IndustrialHeading(){
 const {appearance,reduced}=useAppearance();
 const drawing=useRef<HTMLSpanElement>(null);
 useEffect(()=>{
  const layer=drawing.current;
  const heading=layer?.parentElement;
  if(!layer||!heading||reduced||!matchMedia('(hover: hover) and (pointer: fine)').matches)return;
  const reset=()=>{
   layer.style.removeProperty('--mx');
   layer.style.removeProperty('--my');
  };
  const follow=(event:PointerEvent)=>{
   if(event.pointerType!=='mouse')return;
   const box=heading.getBoundingClientRect();
   layer.style.setProperty('--mx',((event.clientX-box.left)/box.width-.5).toFixed(3));
   layer.style.setProperty('--my',((event.clientY-box.top)/box.height-.5).toFixed(3));
  };
  heading.addEventListener('pointermove',follow);
  heading.addEventListener('pointerleave',reset);
  return ()=>{
   reset();
   heading.removeEventListener('pointermove',follow);
   heading.removeEventListener('pointerleave',reset);
  };
 },[appearance.edition,reduced]);
 if(appearance.edition!=='industrial')return null;
 return <>
  <span className="atlas-contour-motion" ref={drawing} aria-hidden="true"/>
  <span className="ef-tri atlas-print-register" aria-hidden="true"><i/><i/><i/></span>
 </>;
}

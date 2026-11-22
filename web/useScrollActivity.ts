import {useEffect} from 'react';
export function useScrollActivity(){useEffect(()=>{
 const timers=new Map<HTMLElement,ReturnType<typeof setTimeout>>();
 const handle=(e:Event)=>{const el=e.target instanceof HTMLElement?e.target:document.scrollingElement as HTMLElement|null;if(!el)return;el.classList.add('is-scrolling');const old=timers.get(el);if(old)clearTimeout(old);timers.set(el,setTimeout(()=>{el.classList.remove('is-scrolling');timers.delete(el)},900))};
 document.addEventListener('scroll',handle,true);return()=>{document.removeEventListener('scroll',handle,true);timers.forEach((id,el)=>{clearTimeout(id);el.classList.remove('is-scrolling')})};
 },[])}

import {useEffect,useId,useMemo,useRef,type MouseEvent} from 'react';
import {drawDial} from './endfield-dial.js';

type Row={criterion:{id:string};supports:unknown[];opposes:unknown[];pending:unknown[];done:unknown[]};

export default function CoverageDial({rows}:{rows:Row[]}){
 const svg=useRef<SVGSVGElement>(null);
 const heading=useId();
 const sectors=useMemo(()=>[
  {zh:'有证据',en:'Evidence',matches:rows.filter(row=>row.supports.length||row.opposes.length)},
  {zh:'待复核',en:'Review',matches:rows.filter(row=>row.pending.length)},
  {zh:'已记录验证',en:'Validation',matches:rows.filter(row=>row.done.length)},
  {zh:'缺有效证据',en:'Gaps',matches:rows.filter(row=>!row.supports.length&&!row.opposes.length)},
 ],[rows]);

 useEffect(()=>{
  const element=svg.current;
  if(!element)return;
  drawDial(element,{
   sections:sectors.map((sector,index)=>({
    zh:index===3?'缺证据':sector.zh,en:sector.en,big:sector.matches.length,unit:'项',
    href:`#coverage-sector-${index}`,alert:index===3&&sector.matches.length>0,
   })),
   idle:{label:'评价标准',big:rows.length,unit:'项'},
  });
  element.querySelectorAll('a').forEach((link,index)=>{
   const {zh,matches}=sectors[index];
   if(matches.length)link.setAttribute('aria-label',`${zh}：${matches.length}项`);
   else{
    link.removeAttribute('href');
    link.removeAttribute('aria-label');
   }
  });
  return ()=>element.replaceChildren();
 },[rows.length,sectors]);

 function locate(event:MouseEvent<SVGSVGElement>){
  const target=event.target;
  if(!(target instanceof Element))return;
  const href=target.closest('a')?.getAttribute('href');
  if(!href)return;
  event.preventDefault();
  const sector=sectors.find((_,index)=>href===`#coverage-sector-${index}`);
  const id=sector?.matches[0]?.criterion.id;
  const tableRows=event.currentTarget.closest('.project-coverage')?.querySelectorAll<HTMLTableRowElement>('[data-criterion-id]');
  const row=Array.from(tableRows??[]).find(item=>item.dataset.criterionId===id);
  row?.focus();
 }

 return <section className="atlas-coverage-dial" aria-labelledby={heading}>
  <div>
   <h4 id={heading}>证据覆盖索引</h4>
   <p>选择扇区定位首条对应标准。同一标准可同时计入多个扇区。</p>
   <ul>{sectors.map(sector=><li key={sector.en}>
    <span>{sector.zh}</span>
    <strong className={'ef-field ef-state'+(sector.en==='Gaps'&&sector.matches.length?' is-alert':'')}>{sector.matches.length} 项</strong>
   </li>)}</ul>
  </div>
  <svg ref={svg} className="ef-dial" viewBox="0 0 600 600" role="group" aria-label="证据覆盖导航" onClick={locate}/>
 </section>;
}

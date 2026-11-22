import {useEffect,useState} from 'react';
import type {Project} from './projectApi';
export const decisionFields=(v:Project)=>({title:v.title,owner:v.owner,question:v.question,constraints:v.constraints,criteria:v.criteria,recommendation:v.recommendation,open_questions:v.open_questions});
const fieldNames={title:'项目名称',owner:'负责人',question:'决策问题',constraints:'工况与约束',criteria:'评价标准',recommendation:'建议与判断依据',open_questions:'未解问题与后续验证'};
type LocalDecision={baseRevision:number;base:ReturnType<typeof decisionFields>;fields:ReturnType<typeof decisionFields>};
const fresh=(p:Project):LocalDecision=>({baseRevision:p.revision,base:decisionFields(p),fields:decisionFields(p)});
function restore(key:string,p:Project):{local:LocalDecision;error:string}{
 try{const raw=localStorage.getItem(key);if(raw){const v=JSON.parse(raw);const valid=(fields:unknown)=>!!fields&&typeof fields==='object'&&Array.isArray((fields as Project).criteria)&&(fields as Project).criteria.every(c=>!!c&&typeof c==='object'&&typeof c.id==='string'&&!!c.id.trim()&&typeof c.label==='string')&&new Set((fields as Project).criteria.map(c=>c.id)).size===(fields as Project).criteria.length&&['title','owner','question','constraints','recommendation','open_questions'].every(k=>typeof (fields as Record<string,unknown>)[k]==='string');if(v&&Number.isInteger(v.baseRevision)&&v.baseRevision>0&&valid(v.base)&&valid(v.fields))return {local:v,error:''};return {local:fresh(p),error:'本机草稿内容损坏，无法恢复。请核对后手动保存决策。'};}}
 catch{return {local:fresh(p),error:'本机草稿存储不可用或内容损坏，请核对后手动保存决策。'}}
 return {local:fresh(p),error:''};
}
export function useDecisionDraft(project:Project){
 const key=`research-atlas:project-decision:${project.id}`;
 const [initial]=useState(()=>restore(key,project));
 const [storageError,setStorageError]=useState(initial.error),[local,setLocal]=useState(initial.local);
 const dirty=JSON.stringify(local.fields)!==JSON.stringify(local.base);
 const server=decisionFields(project),keys=Object.keys(fieldNames) as (keyof typeof fieldNames)[],same=(a:unknown,b:unknown)=>JSON.stringify(a)===JSON.stringify(b);
 const conflictFields=keys.filter(key=>!same(local.fields[key],local.base[key])&&!same(server[key],local.base[key])&&!same(local.fields[key],server[key])).map(key=>fieldNames[key]);
 const mergedFields=Object.fromEntries(keys.map(key=>[key,same(local.fields[key],local.base[key])?server[key]:local.fields[key]])) as ReturnType<typeof decisionFields>;

 useEffect(()=>{if(!dirty)setLocal(fresh(project))},[project]);
 useEffect(()=>{if(!dirty){try{localStorage.removeItem(key)}catch{setStorageError('本机草稿存储不可用，请在离开前手动保存决策。')}return;}try{localStorage.setItem(key,JSON.stringify(local));setStorageError('')}catch{setStorageError('本机草稿存储不可用；当前修改仅在此页面保留，请在离开前手动保存。')}},[local,key,dirty]);
 function clear(saved:Project){setLocal(fresh(saved));try{localStorage.removeItem(key);setStorageError('')}catch{setStorageError('无法清除本机草稿，请检查浏览器存储权限。')}}
 return {mergedProject:{...project,...mergedFields,revision:project.revision},conflictFields,draft:{...project,...local.fields,revision:local.baseRevision},dirty,baseRevision:local.baseRevision,conflict:dirty&&local.baseRevision!==project.revision,storageError,change:<K extends keyof Project>(key:K,value:Project[K])=>setLocal(s=>({...s,fields:{...s.fields,[key]:value}})),clear};
}

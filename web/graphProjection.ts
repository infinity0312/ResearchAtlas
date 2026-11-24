import type {GraphData} from './GraphCanvas';
export function paperColor(id:string){
 let hash=2166136261;
 for(const character of id)hash=Math.imul(hash^character.charCodeAt(0),16777619);

 // Allocate distinct paper colors across warm and cool ranges.
 const hue=(hash>>>0)%209;
 return `hsl(${hue<49?hue:hue+151} 38% 45%)`;
}
/** Paper nodes are connected only by shared, selected tags. */
export function projectGraph(data:GraphData,similarity=true){
 const owners=new Map<string,string[]>(),groups=new Map<string,string[]>();
 const validTags=new Set(data.tags.map(t=>t.id)),validPapers=new Set(data.papers.map(p=>p.id));
 for(const l of data.links){if(!validTags.has(l.tag_id)||!validPapers.has(l.paper_id))continue;
  const ps=owners.get(l.tag_id)||[];if(!ps.includes(l.paper_id))ps.push(l.paper_id);owners.set(l.tag_id,ps);
  const ts=groups.get(l.paper_id)||[];if(!ts.includes(l.tag_id))ts.push(l.tag_id);groups.set(l.paper_id,ts);
 }
 const pairs=new Map<string,{source:string;target:string;tags:string[]}>();
 for(const [tag,ps] of owners){ps.sort();for(let i=0;i<ps.length;i++)for(let j=i+1;j<ps.length;j++){
  const key=ps[i]+'|'+ps[j];const edge=pairs.get(key)||{source:'p:'+ps[i],target:'p:'+ps[j],tags:[]};edge.tags.push(tag);pairs.set(key,edge);
 }}
 // Broad topic membership is a filter; rare subtopics can support a weak relation.
 const n=data.papers.length,tagById=new Map(data.tags.map(t=>[t.id,t]));
 const weight=(id:string)=>(.2+Math.log((n+1)/((owners.get(id)?.length||0)+1)))*(tagById.get(id)?.kind==='topic'?.15:1);
 const mass=(id:string)=>(groups.get(id)||[]).reduce((sum,t)=>sum+weight(t),0);
 const candidates=[...pairs.values()].filter(e=>e.tags.some(t=>(owners.get(t)?.length||0)<=Math.max(3,n*(tagById.get(t)?.kind==='topic'?.2:.45)))).map(e=>({...e,weight:e.tags.reduce((sum,t)=>sum+weight(t),0)/Math.max(.01,Math.sqrt(mass(e.source.slice(2))*mass(e.target.slice(2))))})).filter(e=>e.weight>=.015).sort((a,b)=>b.weight-a.weight||a.source.localeCompare(b.source)||a.target.localeCompare(b.target));
 const degree=new Map<string,number>();const edges=candidates.filter(e=>{if((degree.get(e.source)||0)>=5||(degree.get(e.target)||0)>=5)return false;degree.set(e.source,(degree.get(e.source)||0)+1);degree.set(e.target,(degree.get(e.target)||0)+1);return true});
 const directed=(data.relations||[]).map(r=>({source:'p:'+r.source_id,target:'p:'+r.target_id,tags:[] as string[],weight:1,kind:r.kind,evidence:r.evidence}));
 const explicit=new Set(directed.map(e=>[e.source,e.target].sort().join('|')));
 return {owners,groups,edges:[...directed,...(similarity?edges.filter(e=>!explicit.has([e.source,e.target].sort().join('|'))).map(e=>({...e,kind:'similarity',evidence:undefined})):[])]};
}

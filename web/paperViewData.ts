import type {GraphData} from './GraphCanvas';

type GraphPaper=GraphData['papers'][number];

export function timelineDate(paper:GraphPaper){
 const date=paper.published?.slice(0,10)||'';
 const year=date.slice(0,4);
 const basis=paper.date_basis;
 if(basis==='published-year'&&/^\d{4}$/.test(year))return {kind:'year',date:year,year} as const;
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date))return {kind:'unknown',date:'',year:''} as const;
 const timestamp=Date.parse(date+'T00:00:00Z');
 if(!Number.isFinite(timestamp)||new Date(timestamp).toISOString().slice(0,10)!==date){
  return {kind:'unknown',date:'',year:''} as const;
 }
 if(basis==='announcement'||basis==='imported')return {kind:basis,date,year:''} as const;
 if(basis&&basis!=='submitted'&&basis!=='published')return {kind:'unknown',date,year:''} as const;
 return {kind:'exact',date,year,timestamp} as const;
}

export function closestByTags(cells:number[][], index:number, limit=5){
 return cells.filter(([i,j,value])=>i===index&&j!==index&&value>0)
  .sort((a,b)=>b[2]-a[2]||a[1]-b[1]).slice(0,limit);
}
export function similarityMatrix(data:GraphData,includeCells=true,population:GraphData=data){
 const sets=new Map(data.papers.map(p=>[p.id,new Set<string>()]));for(const l of data.links)sets.get(l.paper_id)?.add(l.tag_id);
 const populationSets=new Map(population.papers.map(p=>[p.id,new Set<string>()]));for(const l of population.links)populationSets.get(l.paper_id)?.add(l.tag_id);
 const weights=new Map(population.tags.map(t=>[t.id,(t.kind==='topic'?.35:1)*(.2+Math.log((population.papers.length+1)/(1+[...populationSets.values()].filter(s=>s.has(t.id)).length)))]));
 const cells:number[][]=[];
 if(includeCells)data.papers.forEach((a,i)=>data.papers.forEach((b,j)=>{const left=sets.get(a.id)!,right=sets.get(b.id)!;if(!left.size||!right.size)return;const union=new Set([...left,...right]);let shared=0,total=0;for(const t of union){const w=weights.get(t)||0;total+=w;if(left.has(t)&&right.has(t))shared+=w}cells.push([i,j,total?shared/total:0])}));
 return {sets,cells};
}

import {forceSimulation,forceManyBody,forceLink,forceCenter,forceCollide,forceX,forceY} from 'd3-force';
export function createGraphSimulation(nodes:any[],links:any[],timeline=false){
 const years=nodes.map(n=>n.year).filter(y=>y>0);const midpoint=years.length?(Math.min(...years)+Math.max(...years))/2:0;
 return forceSimulation(nodes).stop().alphaDecay(.035).velocityDecay(.35)
 .force('charge',forceManyBody().strength(-330).distanceMax(800))
 .force('link',forceLink(links).id((n:any)=>n.id).distance((e:any)=>195-55*(e.weight||.5)).strength((e:any)=>(.16+.24*(e.weight||.5))/Math.sqrt(Math.max(1,e.source.degree||1,e.target.degree||1))))
 .force('center',forceCenter()).force('collision',forceCollide((n:any)=>Math.max(68,(n.label?.length||6)*6+26)).iterations(3))
 .force('x',forceX((n:any)=>timeline&&n.year?(n.year-midpoint)*55:0).strength((n:any)=>timeline?.16:n.degree===0?.035:.008)).force('y',forceY().strength((n:any)=>n.degree===0?.035:.008));
}

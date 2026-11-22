import {createGraphSimulation} from './graphPhysics';
let initialLayout=true;
let sim:any,nodes:any[]=[],timer:ReturnType<typeof setInterval>|undefined;
const publish=()=>self.postMessage({initialComplete:initialLayout&&sim.alpha()<.006,positions:Object.fromEntries(nodes.map(n=>[n.id,{x:n.x,y:n.y}]))});
function wake(){if(timer)return;timer=setInterval(()=>{sim.tick(2);publish();if(sim.alpha()<.006){clearInterval(timer);timer=undefined}},32)}
self.onmessage=e=>{
 const m=e.data;
 if(m.type==='drag'||m.type==='release'){
  initialLayout=false;const n=nodes.find(n=>n.id===m.id);if(!n)return;
  n.fx=m.type==='drag'?m.x:null;n.fy=m.type==='drag'?m.y:null;
  sim.alpha(.4);wake();return;
 }
 if(timer)clearInterval(timer);timer=undefined;
 initialLayout=true;nodes=m.nodes;nodes.forEach(n=>{if(n.x===0&&n.y===0){delete n.x;delete n.y}});
 sim=createGraphSimulation(nodes,m.links,m.timeline);
 // Show separation progressively; reduced-motion users receive the settled layout.
 sim.tick(m.reducedMotion?160:20);publish();if(!m.reducedMotion)wake();
};

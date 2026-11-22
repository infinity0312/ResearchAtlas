type Rect={x:number;y:number;w:number;h:number};
// Prefer proximity to the pointer, while keeping projected axis labels readable.
export function placeTooltip(width:number,height:number,w:number,h:number,x:number,y:number,labels:Rect[]){
 const clamp=(v:number,max:number)=>Math.max(8,Math.min(max-8,v));
 const candidates=[{x:x+20,y:y+20},{x:x-w-20,y:y+20},{x:x+20,y:y-h-20},{x:x-w-20,y:y-h-20}];
 for(let cy=8;cy<=height-h-8;cy+=20)for(let cx=8;cx<=width-w-8;cx+=20)candidates.push({x:cx,y:cy});
 let best={x:8,y:8},score=Infinity;
 for(const c of candidates){const p={x:clamp(c.x,width-w),y:clamp(c.y,height-h)};
  const overlaps=labels.reduce((sum,r)=>sum+Math.max(0,Math.min(p.x+w,r.x+r.w+6)-Math.max(p.x,r.x-6))*Math.max(0,Math.min(p.y+h,r.y+r.h+6)-Math.max(p.y,r.y-6)),0);
  const coversPointer=x>=p.x-12&&x<=p.x+w+12&&y>=p.y-12&&y<=p.y+h+12;
  const cost=overlaps*1e6+(coversPointer?1e5:0)+Math.hypot(p.x+w/2-x,p.y+h/2-y);
  if(cost<score){score=cost;best=p}
 }return best;
}

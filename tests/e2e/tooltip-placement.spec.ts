import {test,expect} from '@playwright/test';
import {placeTooltip} from '../../web/spatial/tooltipPlacement';
test('hover card avoids both axes near matrix corners and stays within viewport',()=>{
 for(const width of [390,834]){
  const labels=[...Array.from({length:24},(_,i)=>({x:40+i*(width-60)/24,y:120,w:14,h:20})),...Array.from({length:16},(_,i)=>({x:20,y:145+i*20,w:18,h:18}))];
  for(const [x,y] of [[60,145],[width-35,145],[60,410],[width-35,410]]){
   const w=Math.min(340,width-16),h=110,p=placeTooltip(width,530,w,h,x,y,labels);
   expect(p.x).toBeGreaterThanOrEqual(8);expect(p.x+w).toBeLessThanOrEqual(width-8);expect(p.y+h).toBeLessThanOrEqual(522);
   for(const r of labels)expect(p.x<r.x+r.w&&p.x+w>r.x&&p.y<r.y+r.h&&p.y+h>r.y).toBeFalsy();
  }
 }
});

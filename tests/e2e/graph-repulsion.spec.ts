import {test,expect} from '@playwright/test';
test('repulsion animates after opening and continues while a node is dragged',async({page})=>{
 const papers=Array.from({length:12},(_,i)=>({id:'repulsion-'+i,title:'Repulsion test '+i,label:'N'+i}));
 const tags=[{id:'shared',name:'Shared method',kind:'method',description:'fixture',count:12,archived:false}];
 const links=papers.map(p=>({paper_id:p.id,tag_id:'shared',source:'manual'}));
 await page.route('**/api/graph?*',r=>r.fulfill({json:{papers,tags,links,total:12,truncated:false}}));
 await page.goto('/#page=map');const graph=page.locator('.atlas-network');await expect(graph).toHaveAttribute('data-ready','true');
 const movement=await graph.evaluate(async el=>{const node=el.querySelector('[data-node-id]')!;const positions=new Set<string|null>();for(let i=0;i<30;i++){await new Promise(requestAnimationFrame);positions.add(node.getAttribute('transform'))}return positions.size});expect(movement).toBeGreaterThan(3);
 await graph.scrollIntoViewIfNeeded();const node=graph.locator('[data-node-id]').first(),neighbor=graph.locator('[data-node-id]').nth(1);const box=await node.locator('.node-core').boundingBox();expect(box).not.toBeNull();
 await page.mouse.move(box!.x+box!.width/2,box!.y+box!.height/2);await page.mouse.down();
 const before=await neighbor.getAttribute('transform');for(let i=1;i<=12;i++){await page.mouse.move(box!.x+box!.width/2+i*5,box!.y+box!.height/2+i*2);await page.evaluate(()=>new Promise(requestAnimationFrame))}
 expect(await neighbor.getAttribute('transform')).not.toBe(before);await page.mouse.up();
});

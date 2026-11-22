import {test,expect} from '@playwright/test';
import {projectGraph} from '../../web/graphProjection';
const papers=['a','b','c'].map(id=>({id,title:'Paper '+id}));
const tags=['x','y','z'].map(id=>({id,name:id,kind:'method',description:'',count:2,archived:false}));
const links=[['a','x'],['b','x'],['a','x'],['a','z'],['b','z'],['c','y'],['missing','x'],['a','missing']].map(([paper_id,tag_id])=>({paper_id,tag_id,source:'manual'}));
test('paper projection deduplicates shared tags and preserves isolated papers',()=>{
 const graph=projectGraph({papers,tags,links,total:3,truncated:false});
 expect(graph.edges).toEqual([expect.objectContaining({source:'p:a',target:'p:b',tags:['x','z']})]);
 expect(graph.groups.get('c')).toEqual(['y']);
 expect(graph.owners.get('x')).toEqual(['a','b']);
});
test('selecting tags filters paper nodes and all-match narrows the selection',async({page})=>{
 await page.route('**/api/tags',r=>r.fulfill({json:tags}));
 await page.route('**/api/graph?*',r=>{
  const q=new URL(r.request().url()).searchParams,ids=q.getAll('tag_ids');
  const ps=papers.filter(p=>ids.length&&(q.get('match')==='all'?ids.every(id=>links.some(l=>l.paper_id===p.id&&l.tag_id===id)):ids.some(id=>links.some(l=>l.paper_id===p.id&&l.tag_id===id))));
  return r.fulfill({json:{papers:ps,tags:tags.filter(t=>ids.includes(t.id)),links:links.filter(l=>ids.includes(l.tag_id)&&ps.some(p=>p.id===l.paper_id)),total:ps.length,truncated:false}});
 });
 await page.goto('/#page=map');await page.getByRole('button',{name:'切换标签筛选面板'}).click();
 await page.getByRole('button',{name:'清空选择',exact:true}).click();await page.locator('.graph-tag-list label').filter({hasText:'x'}).getByRole('checkbox').check();
 await expect(page.locator('[data-node-id]')).toHaveCount(2);
 await expect(page.locator('[data-node-id="p:c"]')).toHaveCount(0);
 await expect(page.locator('.network-edge')).toHaveCount(0);
 await page.locator('.graph-tag-list label').filter({hasText:'y'}).getByRole('checkbox').check();
 await expect(page.locator('[data-node-id]')).toHaveCount(3);
 await page.getByLabel('标签匹配方式').selectOption('all');
 await expect(page.getByRole('heading',{name:'没有匹配的文献'})).toBeVisible();
 await expect(page.locator('[data-node-id]')).toHaveCount(0);
});

test('broad topics do not create cliques and specific edges have bounded degree',()=>{
 const ps=Array.from({length:30},(_,i)=>({id:String(i),title:String(i)}));
 const ts=[{...tags[0],id:'broad',kind:'topic'},...Array.from({length:3},(_,i)=>({...tags[0],id:'m'+i}))];
 const ls=ps.flatMap((p,i)=>[{paper_id:p.id,tag_id:'broad',source:'manual'},{paper_id:p.id,tag_id:'m'+Math.floor(i/10),source:'manual'}]);
 const g=projectGraph({papers:ps,tags:ts,links:ls,total:30,truncated:false});
 expect(g.edges.length).toBeGreaterThan(0);expect(g.edges.length).toBeLessThanOrEqual(75);
 for(const p of ps)expect(g.edges.filter(e=>e.source==='p:'+p.id||e.target==='p:'+p.id).length).toBeLessThanOrEqual(5);
 expect(g.edges.every(e=>e.tags.some(t=>t.startsWith('m')))).toBe(true);
 expect(projectGraph({papers:ps,tags:ts,links:ls.filter(l=>l.tag_id==='broad'),total:30,truncated:false}).edges).toHaveLength(0);
});

test('links attract related papers into a closer equilibrium',async()=>{
 const {createGraphSimulation}=await import('../../web/graphPhysics');
 const distance=(linked:boolean)=>{const ns=[{id:'a',x:-300,y:0},{id:'b',x:300,y:0}];const sim=createGraphSimulation(ns,linked?[{source:'a',target:'b',weight:1}]:[]);sim.tick(200);sim.stop();return Math.hypot(ns[0].x-ns[1].x,ns[0].y-ns[1].y)};
 expect(distance(true)).toBeLessThan(distance(false)*.65);
});

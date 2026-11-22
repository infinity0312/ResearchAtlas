import {test,expect} from '@playwright/test';
import {writeFileSync} from 'node:fs';
import {projectGraph} from '../../web/graphProjection';

test('dense graph settles off-thread and supports focus, zoom, themes and reading',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 const tags=Array.from({length:24},(_,i)=>({id:'visual-'+i,name:['等变表示','电荷密度预测','材料逆向设计','图神经网络'][i%4]+' '+i,kind:['method','problem','topic','custom'][i%4],description:'仅用于隔离的图谱交互测试',count:15,archived:false}));
 const papers=Array.from({length:120},(_,i)=>({id:`2609.${String(i).padStart(5,'0')}`,title:'Visualization test paper '+i}));
 const relations=papers.slice(1).map((p,i)=>({id:'ref'+i,source_id:p.id,target_id:papers[i].id,kind:'cites',evidence:{page:1,quote:'Fixture citation'}}));
 const links=papers.flatMap((p,i)=>[0,1,2].map(j=>({paper_id:p.id,tag_id:tags[(i+j*7)%tags.length].id,source:j?'analysis':'manual'})));
 await page.route('**/api/tags',route=>route.fulfill({json:tags}));
 await page.route('**/api/tags?*',route=>route.fulfill({json:tags}));
 await page.route('**/api/graph?*',route=>route.fulfill({json:new URL(route.request().url()).searchParams.has('tag_ids')?{papers,tags,links,relations,total:120,truncated:false}:{papers:[],tags:[],links:[],total:0,truncated:false}}));
 await page.goto('/#page=map');await page.getByRole('button',{name:'切换标签筛选面板'}).click();
 // Bring the control into the viewport before measuring selection-to-layout latency.
 await page.getByRole('button',{name:'选择当前列表',exact:true}).scrollIntoViewIfNeeded();
 const start=Date.now();await page.getByRole('button',{name:'选择当前列表',exact:true}).click();await expect(page.locator('.atlas-network')).toHaveAttribute('data-ready','true');
 const elapsed=Date.now()-start;const layoutMs=Number(await page.locator('.atlas-network').getAttribute('data-layout-ms'));expect(layoutMs).toBeLessThan(2000);expect(elapsed).toBeLessThan(8000);
 await expect(page.locator('[data-node-id]')).toHaveCount(120);await expect(page.locator('.network-edge')).toHaveCount(relations.length);
 await page.locator('.relation-panel').screenshot({path:'docs/graph-polish-fixture.png'});
 await page.locator('.paper-legend > summary').click();
 const tag=page.getByRole('button',{name:'聚焦文献：Visualization test paper 0',exact:true});await tag.focus();await expect(page.locator('.network-inspector')).toContainText('等变表示 0');expect(await page.locator('.network-node.faded').count()).toBeGreaterThan(0);
 await tag.click();await page.getByRole('button',{name:'取消节点聚焦'}).click();await expect(page.locator('.network-inspector')).toHaveCount(0);
 const before=await page.locator('.network-tools span').innerText();await page.getByRole('button',{name:'放大图谱',exact:true}).click();await expect.poll(()=>page.locator('.network-tools span').innerText()).not.toEqual(before);await page.getByRole('button',{name:'适应画布',exact:true}).click();
 await expect(page.locator('.node-label')).toHaveCount(0);await expect(page.locator('[data-node-id^="t:"]')).toHaveCount(0);await expect(page.locator('.paper-legend-row')).toHaveCount(120);
 await expect(page.locator('.relation-panel')).toHaveClass(/graph-light/);await page.getByRole('button',{name:'切换深色画布'}).click();await expect(page.locator('.relation-panel')).toHaveClass(/graph-dark/);await page.getByRole('button',{name:'切换浅色画布'}).click();
 await page.getByRole('button',{name:'专注视图',exact:true}).click();await expect(page.locator('.relation-panel')).toHaveClass(/graph-expanded/);await page.keyboard.press('Escape');await expect(page.locator('.relation-panel')).not.toHaveClass(/graph-expanded/);
 await page.getByRole('button',{name:'切换标签筛选面板'}).click();await expect(page.locator('.graph-controls')).not.toBeVisible();await page.getByRole('button',{name:'切换标签筛选面板'}).click();
 await page.locator('[data-node-id="p:2609.00000"]').focus();await page.keyboard.press('Enter');await expect(page.getByRole('dialog',{name:'论文阅读'})).toBeVisible();await page.keyboard.press('Escape');
 await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'适应画布',exact:true}).click();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 expect(errors).toEqual([]);
 writeFileSync('docs/graph-render-benchmark.json',JSON.stringify({fixture:true,papers:120,tags:24,memberships:360,relationships:projectGraph({papers,tags,links,total:120,truncated:false}).edges.length,ready_ms:elapsed,worker_initial_layout_ms:layoutMs,scope:'Playwright Chromium, includes query interception, lazy module load and worker layout; not a production-scale benchmark'},null,2));
});

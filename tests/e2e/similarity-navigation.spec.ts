import {test,expect} from '@playwright/test';
test('dense similarity matrix pans, retains docked axes and suppresses drag selection',async({page})=>{
 test.setTimeout(120000);
 await page.addInitScript(()=>{localStorage.setItem('atlas.appearance.v1',JSON.stringify({edition:'prism',effects:'auto',motion:'reduced'}));sessionStorage.setItem('atlas.terminal.entered','1')});
 const papers=Array.from({length:32},(_,i)=>({id:String(i),title:'Paper '+i,label:'P'+i,published:'2025-01-01'}));
 await page.route('**/api/graph?*',r=>r.fulfill({json:{papers,tags:[{id:'t',name:'Shared',kind:'topic'}],links:papers.map(p=>({paper_id:p.id,tag_id:'t'})),relations:[],total:32,truncated:false}}));
 await page.goto('/#page=map');await page.getByLabel('图谱视图',{exact:true}).selectOption('similarity');await page.getByRole('button',{name:'切换二维与三维',exact:true}).click();
 const host=page.locator('.relief-host');await host.scrollIntoViewIfNeeded();await expect(host).toHaveAttribute('data-ready','true');
 for(let i=0;i<5;i++)await page.getByLabel('放大数据空间',{exact:true}).click();
 await expect.poll(async()=>Number(await host.getAttribute('data-zoom'))).toBeGreaterThan(3);
 await host.scrollIntoViewIfNeeded();const area=(await host.boundingBox())!;
 await page.mouse.move(area.x+area.width*.5,area.y+150);await page.mouse.down();await page.mouse.move(area.x+area.width*.5+110,area.y+210,{steps:12});await page.mouse.up();
 await expect.poll(async()=>Math.abs(Number(await host.getAttribute('data-pan-x')))).toBeGreaterThan(.2);
 await expect(page.locator('.relief-paper')).toHaveCount(0);
 const ticks=await host.locator('.relief-label[data-axis]').evaluateAll(els=>els.filter(e=>getComputedStyle(e).visibility==='visible').map(e=>({axis:e.getAttribute('data-axis'),x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y})));
 expect(ticks.filter(t=>t.axis==='column').length).toBeGreaterThan(2);expect(ticks.filter(t=>t.axis==='row').length).toBeGreaterThan(2);
 expect(ticks.filter(t=>t.axis==='column').every(t=>Math.abs(t.y-(area.y+20))<16)).toBeTruthy();
 await page.getByRole('button',{name:'全览',exact:true}).click();await expect(host).toHaveAttribute('data-pan-x','0.000');await expect(host).toHaveAttribute('data-zoom','1.000');
});

test('opportunity chart zoom and expansion preserve the chart',async({page})=>{
 await page.addInitScript(()=>sessionStorage.setItem('atlas.terminal.entered','1'));
 await page.route('**/api/trends/data?*',async route=>{const response=await route.fetch(),body=await response.json();body.series=body.series.map((r:any,i:number)=>({...r,insight:{x:45+i*8,y:50+i*5,periods:[],status:'可比较'}}));await route.fulfill({json:body})});
 await page.goto('/#page=trends');const plot=page.locator('.opportunity-plot');await expect(plot).toBeVisible();
 await page.getByLabel('放大创新空间图',{exact:true}).click();await expect(page.getByLabel('创新空间缩放比例')).toHaveText('133%');
 await page.getByRole('button',{name:'展开图表',exact:true}).click();await expect(page.locator('.opportunity-chart')).toHaveCSS('height','820px');
 await page.getByLabel('重置创新空间图',{exact:true}).click();await expect(page.getByLabel('创新空间缩放比例')).toHaveText('100%');
 await expect(plot.locator('canvas')).toBeVisible();
});

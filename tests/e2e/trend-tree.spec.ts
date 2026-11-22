import {test,expect} from '@playwright/test';
test('trend directions are collapsed under their whole-domain parent',async({page})=>{
 await page.goto('/#page=trends');const toggle=page.getByRole('button',{name:'展开或收起：分子与材料 · 全领域',exact:true});await expect(toggle).toHaveAttribute('aria-expanded','false',{timeout:15000});await expect(page.getByLabel('选择趋势方向：分子性质预测',{exact:true})).toHaveCount(0);
 await toggle.click();await expect(page.getByLabel('选择趋势方向：分子性质预测',{exact:true})).toBeVisible();await expect(page.getByLabel('选择趋势方向：分子生成',{exact:true})).toBeVisible();await expect(page.getByLabel('选择趋势方向：蛋白质设计',{exact:true})).toHaveCount(0);
 await page.getByLabel('选择趋势方向：分子与材料 · 全领域',{exact:true}).check();await expect(toggle).toHaveAttribute('aria-expanded','true');await toggle.click();await expect(page.getByLabel('选择趋势方向：分子与材料 · 全领域',{exact:true})).toBeChecked();await expect(page.getByLabel('选择趋势方向：分子生成',{exact:true})).toHaveCount(0);
 await page.setViewportSize({width:390,height:844});await toggle.click();expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});


for(const width of [390,1024,1440])test(`trend chart stays bounded through expanding trees and details at ${width}`,async({page})=>{
 await page.setViewportSize({width,height:900});
 await page.route('**/api/trends/data?*',async route=>{const response=await route.fetch();const body=await response.json();body.series=body.series.map((r:any)=>({...r,points:r.points.map((p:any,i:number)=>({...p,count:i*12+8}))}));await route.fulfill({json:body})});
 await page.goto('/#page=trends');const chart=page.locator('.macro-chart');await expect(chart).toBeVisible();
 const initial=(await chart.boundingBox())!;
 for(let cycle=0;cycle<2;cycle++){
  for(const button of await page.locator('.trend-tree-toggle').all())await button.click();
  await expect.poll(async()=>Math.abs((await chart.boundingBox())!.height-initial.height)).toBeLessThan(2);
  const details=page.locator('.trend-details');await details.locator('summary').click();
  await expect.poll(async()=>Math.abs((await chart.boundingBox())!.height-initial.height)).toBeLessThan(2);
  await expect.poll(async()=>Math.abs((await chart.locator('canvas').boundingBox())!.height-initial.height)).toBeLessThan(2);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
 }
 expect(initial.height).toBeGreaterThanOrEqual(330);expect(initial.height).toBeLessThanOrEqual(470);
 if(width===1440){for(const button of await page.locator('.trend-tree-toggle').all())await button.click();await page.locator('.trends-layout').screenshot({path:'docs/trends-expanded-stable.png',animations:'disabled'})}
});

test('selection retains canvas during delayed response and panels align',async({page})=>{
 await page.route('**/api/trends/data?*',async route=>{const response=await route.fetch();const body=await response.json();body.series=body.series.map((r:any)=>({...r,points:r.points.map((p:any,i:number)=>({...p,count:i*12+8}))}));await new Promise(resolve=>setTimeout(resolve,700));await route.fulfill({json:body})});
 await page.goto('/#page=trends');const chart=page.locator('.macro-chart');await expect(chart).toBeVisible();
 const canvas=await chart.locator('canvas').elementHandle();const initial=(await chart.boundingBox())!.height;
 await page.getByRole('button',{name:'展开或收起：分子与材料 · 全领域',exact:true}).click();
 await page.getByLabel('选择趋势方向：分子生成',{exact:true}).uncheck();
 await expect(page.locator('.trend-main')).toHaveAttribute('aria-busy','true');
 expect(await canvas!.evaluate(el=>el.isConnected)).toBe(true);await expect(page.locator('.trend-empty')).toHaveCount(0);
 await expect(chart).toHaveAttribute('data-series-count','1');expect(await canvas!.evaluate(el=>el.isConnected)).toBe(true);
 const left=(await page.locator('.trend-controls').boundingBox())!,right=(await page.locator('.trend-main').boundingBox())!;
 expect(Math.abs(left.height-right.height)).toBeLessThan(2);expect(Math.abs((await chart.boundingBox())!.height-initial)).toBeLessThan(2);
 await page.locator('.trends-layout').screenshot({path:'docs/trends-selection-stable.png',animations:'disabled'});
});

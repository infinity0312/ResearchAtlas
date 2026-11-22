import {test,expect} from '@playwright/test';
test('PDF switching keeps reader frame and reuses the open document',async({page})=>{
 let requests=0;page.on('request',r=>{if(r.url().includes('/api/paper/pdf?'))requests++});
 await page.goto('/#page=papers');await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 const dialog=page.getByRole('dialog',{name:'论文阅读'}),tabs=dialog.locator('.tabs');await dialog.evaluate(async el=>{await Promise.all(el.getAnimations().map(a=>a.finished))});const before=await dialog.boundingBox(),tabBefore=await tabs.boundingBox();
 await page.getByRole('button',{name:'原始 PDF',exact:true}).click();await expect(page.getByRole('img',{name:'原始论文 PDF · 第 1 页',exact:true})).toBeVisible();
 const after=await dialog.boundingBox(),tabAfter=await tabs.boundingBox();expect(after!.y).toBeCloseTo(before!.y,0);expect(after!.height).toBeCloseTo(before!.height,0);expect(tabAfter!.y).toBeCloseTo(tabBefore!.y,0);
 const count=requests;await page.getByLabel('PDF 页码',{exact:true}).fill('2');await page.getByRole('button',{name:'论文摘要',exact:true}).click();await page.getByRole('button',{name:'原始 PDF',exact:true}).click();await expect(page.getByLabel('PDF 页码',{exact:true})).toHaveValue('2');expect(requests).toBe(count);
 await page.screenshot({path:'docs/pdf-stable-reader.png'});
});
test('opportunity plot has no regions or quadrant captions',async({page})=>{
 await page.route('**/api/trends/data?*',r=>r.fulfill({json:{series:[{id:'preset-0',name:'分子性质预测',query:'ti:molecular',color:'#327c72',growth:30,points:[{period:'2023',count:100,partial:false},{period:'2024',count:120,partial:false},{period:'2025',count:150,partial:false}],insight:{x:67,y:58,growth:30,acceleration:5,status:'可比较',rebound:false,periods:[]}}]}}));
 await page.goto('/#page=trends');await expect(page.locator('.opportunity-chart')).toBeVisible();await expect(page.locator('.opportunity-chart')).toHaveAttribute('data-series-count','1');await expect(page.locator('.opportunity-zones')).toHaveCount(0);
});

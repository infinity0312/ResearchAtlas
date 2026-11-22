import {test,expect} from '@playwright/test';

test('library abstracts unfold at the selected paper and survive reading without writes',async({page})=>{
 const writes:string[]=[];page.on('request',r=>{if(r.url().includes('/api/')&&!['GET','HEAD'].includes(r.method()))writes.push(r.url())});
 await page.goto('/#page=papers&days=0');
 await page.getByRole('textbox',{name:'搜索标题或摘要'}).fill('Protein sequence');
 const row=page.locator('.paper-row');await expect(row).toHaveCount(1);
 const title=row.locator('.paper-title'),before=await title.boundingBox();
 const toggle=row.getByRole('button',{name:'摘要与分析概要',exact:true});await toggle.click();
 await expect(toggle).toHaveAttribute('aria-expanded','true');await expect(row.locator('.paper-inline-brief')).toContainText('作者摘要');
 expect(Math.abs((await title.boundingBox())!.y-before!.y)).toBeLessThan(2);
 await row.getByRole('button',{name:'进入全文阅读',exact:true}).click();
 const reader=page.getByRole('dialog',{name:'论文阅读',exact:true});await expect(reader).toBeVisible();await reader.press('Escape');
 await expect(reader).toHaveCount(0);await expect(row.locator('.paper-inline-brief')).toBeVisible();
 await expect(page.getByRole('textbox',{name:'搜索标题或摘要'})).toHaveValue('Protein sequence');
 await expect(row.getByRole('button',{name:'进入全文阅读',exact:true})).toBeFocused();
 await row.locator('.paper-inline-brief').press('Escape');await expect(toggle).toBeFocused();await expect(toggle).toHaveAttribute('aria-expanded','false');
 expect(writes).toEqual([]);
});

for(const width of [390,1024,1440,1920])test(`discovery pages share a contained local workspace at ${width}`,async({page})=>{
 await page.setViewportSize({width,height:950});
 await page.addInitScript(()=>{sessionStorage.setItem('atlas.terminal.entered','1');localStorage.setItem('atlas.appearance.v1',JSON.stringify({edition:'classic',effects:'off',motion:'reduced'}))});
 const left:number[]=[];
 for(const route of ['papers','map','trends']){
  await page.goto('/#page='+route);await expect(page.locator('.page-heading h1')).toBeVisible();
  await expect(page.locator(route==='papers'?'.paper-panel':route==='map'?'.hierarchy-panel':'.trends-layout')).toBeVisible();
  const heading=await page.locator('.page-heading').boundingBox();left.push(heading!.x);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  if(route==='papers'){
   await page.locator('.paper-row .paper-brief-toggle').first().click();
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  }
  if(route==='map'){
   await page.getByRole('navigation',{name:'地图章节'}).getByRole('button',{name:'文献联系',exact:true}).click();
   await expect(page.getByRole('navigation',{name:'地图章节'}).getByRole('button',{name:'文献联系',exact:true})).toHaveAttribute('aria-current','location');
   await expect(page.locator('.relation-panel')).toBeInViewport();
  }
 }
 expect(Math.max(...left)-Math.min(...left)).toBeLessThan(2);
});

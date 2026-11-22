import {test,expect} from '@playwright/test';
for(const [width,height] of [[320,640],[844,390],[390,844],[768,1024],[1024,768],[1366,768],[1920,1080],[2560,1440]]){
 test(`workspace fits ${width}x${height}`,async({page})=>{
 const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
 await page.setViewportSize({width,height});
 for(const name of ['overview','papers','map','trends','surveys','notes','jobs','settings']){
  await page.goto('/#page='+name);await expect(page.locator('.page-heading h1')).toBeVisible();await expect(page.locator('main .loading')).toHaveCount(0,{timeout:15000});await page.locator('.page-footer').scrollIntoViewIfNeeded();
  const bad=await page.evaluate(()=>({width:document.documentElement.scrollWidth,viewport:innerWidth,items:[...document.querySelectorAll('main *')].filter(el=>{const r=el.getBoundingClientRect();return r.width&&r.right>innerWidth+1&&getComputedStyle(el).position!=='absolute'}).slice(0,5).map(el=>el.className)}));expect(bad.width,JSON.stringify({name,...bad})).toBeLessThanOrEqual(width);
 }
 if(width<=900){await page.getByRole('button',{name:'展开导航'}).click();await expect(page.getByRole('button',{name:'发现论文',exact:true})).toBeVisible();await page.getByRole('button',{name:'发现论文',exact:true}).click();await expect(page.getByRole('button',{name:'展开导航'})).toHaveAttribute('aria-expanded','false')}
 await page.goto('/#page=overview');await page.screenshot({path:`docs/workspace-${width}.png`,animations:'disabled'});await page.goto('/#page=papers');await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();const dialog=page.getByRole('dialog',{name:'论文阅读'});await expect(dialog).toBeVisible();const box=await dialog.boundingBox();expect(box!.width).toBeLessThanOrEqual(width);expect(box!.height).toBeLessThanOrEqual(height);await page.screenshot({path:`docs/responsive-${width}.png`,animations:'disabled'});expect(errors).toEqual([]);
 });
}

import {test,expect} from '@playwright/test';
for(const edition of ['classic','prism'])test(`sidebar keeps an opaque stable workspace (${edition})`,async({page})=>{
 await page.addInitScript(edition=>{sessionStorage.setItem('atlas.terminal.entered','1');localStorage.setItem('atlas.appearance.v1',JSON.stringify({edition,effects:'off',motion:'system'}))},edition);
 await page.goto('/#page=overview');await expect(page.locator('.page-heading h1')).toContainText('研究概览');
 const main=await page.locator('main.page-transition').elementHandle();
 for(const name of ['领域趋势','笔记系列','发现论文','研究概览']){
  await page.getByRole('button',{name,exact:true}).click();await expect(page.locator('.page-heading h1')).toContainText(name);
  expect(await main!.evaluate(el=>el.isConnected)).toBeTruthy();
  expect(await page.locator('main.page-transition').evaluate(el=>({opacity:getComputedStyle(el).opacity,animation:getComputedStyle(el).animationName}))).toEqual({opacity:'1',animation:'none'});
 }
 await page.getByRole('button',{name:'领域趋势',exact:true}).click();await page.getByRole('button',{name:'后台任务',exact:true}).click();await expect(page.locator('.page-heading h1')).toContainText('后台任务');
});
test('a slow route import preserves the current page and cannot replace a newer selection',async({page})=>{
 await page.addInitScript(()=>sessionStorage.setItem('atlas.terminal.entered','1'));
 let release:(()=>void)|undefined;
 await page.route('**/Trends-*.js',async route=>{await new Promise<void>(resolve=>{release=resolve});await route.continue()});
 await page.goto('/#page=overview');await expect(page.locator('.page-heading h1')).toContainText('研究概览');
 await page.getByRole('button',{name:'领域趋势',exact:true}).click();await expect.poll(()=>!!release).toBeTruthy();
 await expect(page.locator('.page-heading h1')).toContainText('研究概览');
 await page.getByRole('button',{name:'后台任务',exact:true}).click();await expect(page.locator('.page-heading h1')).toContainText('后台任务');
 release!();await page.waitForLoadState('networkidle');await expect(page.locator('.page-heading h1')).toContainText('后台任务');
});

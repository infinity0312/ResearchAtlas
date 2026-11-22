import {test,expect} from '@playwright/test';
for(const scheme of ['light','dark'] as const){
 test(`PDF styles stay inside reader under ${scheme} system appearance`,async({page})=>{
  await page.emulateMedia({colorScheme:scheme});await page.goto('/#page=papers');
  const sidebar=()=>page.locator('.sidebar').evaluate(el=>{const s=getComputedStyle(el),b=el.getBoundingClientRect();return {background:s.backgroundColor,color:s.color,width:b.width,left:b.left}});
  const before=await sidebar();await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'论文阅读'});const beforeBox=await dialog.boundingBox();
  await page.getByRole('button',{name:'原始 PDF',exact:true}).click();await expect(page.getByRole('img',{name:'原始论文 PDF · 第 1 页',exact:true})).toBeVisible();
  expect(await sidebar()).toEqual(before);const afterBox=await dialog.boundingBox();expect(afterBox!.width).toBeCloseTo(beforeBox!.width,0);expect(afterBox!.x).toBeGreaterThanOrEqual(0);expect(afterBox!.y).toBeGreaterThanOrEqual(0);
  expect(await dialog.evaluate(el=>el.getBoundingClientRect().right<=innerWidth)).toBe(true);
  await page.getByRole('button',{name:'相关文献',exact:true}).click();await expect(page.locator('.related-card').first()).toBeVisible();await page.keyboard.press('Escape');await expect(dialog).toHaveCount(0);expect(await sidebar()).toEqual(before);
 });
}
test('trend chart spacing is independent of direction list height',async({page})=>{
 await page.goto('/#page=trends');await expect(page.locator('.opportunity-panel')).toBeVisible();
 const space=await page.locator('.trend-main').evaluate(el=>{const panel=el.getBoundingClientRect(),last=el.querySelector('.trend-source')!.getBoundingClientRect();return panel.bottom-last.bottom});expect(space).toBeLessThan(30);
 await page.screenshot({path:'docs/layout-trends-refined.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await expect(page.locator('.page-footer')).not.toContainText('独立核验');
});

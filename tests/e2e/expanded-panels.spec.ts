import {test,expect} from '@playwright/test';
for(const width of [390,1024,1440])test(`expanded panels stay contained at ${width}`,async({page,request})=>{
 await page.setViewportSize({width,height:900});await request.post('/api/tags/import-analysis',{headers:{'X-Atlas-Client':'1'}});
 for(const route of ['trends','map']){
  await page.goto('/#page='+route);await expect(page.locator('.page-heading')).toBeVisible();
  if(route==='map'){await expect(page.locator('.atlas-network')).toHaveAttribute('data-ready','true');await page.getByRole('button',{name:'切换标签筛选面板'}).click()}
  for(const summary of await page.locator('main details > summary').all()){if(await summary.isVisible()&&!await summary.evaluate(el=>el.parentElement?.hasAttribute('open'))){await summary.scrollIntoViewIfNeeded();await summary.click();}}
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  if(route==='trends'&&width===1440){const a=await page.locator('.trend-controls').boundingBox(),b=await page.locator('.trend-main').boundingBox();expect(Math.abs(a!.y-b!.y)).toBeLessThan(3);await page.locator('.trends-layout').screenshot({path:'docs/trends-balanced.png',animations:'disabled'})}
 }
});

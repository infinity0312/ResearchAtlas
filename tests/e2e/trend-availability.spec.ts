import {test,expect} from '@playwright/test';
test('growth-only directions remain visible without inventing opportunity scores',async({page})=>{
 await page.addInitScript(()=>{localStorage.setItem('atlas.trends.selection',JSON.stringify({ids:['preset-0','preset-1'],start:'2020',end:'2025',interval:'year'}));sessionStorage.setItem('atlas.terminal.entered','1')});
 let complete=false;
 await page.route('**/api/trends/data?*',async route=>{const response=await route.fetch(),body=await response.json();body.series=body.series.map((r:any,i:number)=>({...r,insight:{x:30+i*35,y:complete&&i===0?70:null,periods:[],status:'等待核查'}}));await route.fulfill({json:body})});
 await page.goto('/#page=trends');const pending=page.getByRole('region',{name:'创新空间待核查的方向'});
 await expect(pending).toHaveAttribute('data-series-count','2');await expect(page.locator('.opportunity-chart')).toHaveAttribute('data-series-count','0');await expect(page.locator('.opportunity-plot')).toBeHidden();
 await expect(pending.getByRole('button',{name:/分子性质预测，增长动能 30/})).toBeVisible();
 for(const width of [390,1440]){await page.setViewportSize({width,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)}
 complete=true;await page.reload();await expect(pending).toHaveAttribute('data-series-count','1');await expect(page.locator('.opportunity-chart')).toHaveAttribute('data-series-count','1');await expect(page.locator('.opportunity-plot')).toBeVisible();
});

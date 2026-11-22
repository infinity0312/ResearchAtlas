import {test,expect} from '@playwright/test';
test('jobs show execution state and scrollbars fade after scrolling',async({page})=>{
 await page.route('**/api/jobs',route=>route.fulfill({json:[{id:'one',kind:'explore',status:'running',created:'2026-09-26',progress:42,message:'正在拉取论文',payload:{domain_ids:['molecules'],start:'1991-01-01',end:'1991-12-31'},result:{stage:'search'}}]}));
 await page.goto('/#page=jobs');await expect(page.locator('.job-status-badge')).toHaveText('执行中');await expect(page.locator('.job-main')).toContainText('分子与材料');await expect(page.locator('.job-main')).toContainText('检索 · 42%');
 const el=page.locator('.sidebar');await el.dispatchEvent('scroll');await expect(el).toHaveClass(/is-scrolling/);await expect(el).not.toHaveClass(/is-scrolling/,{timeout:3000});
 await expect(page.locator('.job-row')).toBeVisible();await page.locator('.job-row').scrollIntoViewIfNeeded();await page.screenshot({path:'docs/jobs-state.png',animations:'disabled'});
});

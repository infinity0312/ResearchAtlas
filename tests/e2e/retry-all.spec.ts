import {test,expect} from '@playwright/test';
test('batch retry submits once and shows returned counts',async({page})=>{
 await page.route('**/api/jobs',r=>r.fulfill({json:[{id:'failed',kind:'trends',status:'failed',payload:{},result:{},progress:0,message:'网络错误',created:'2026-09-26'}]}));
 let calls=0;await page.route('**/api/jobs/retry-all',r=>{calls++;return r.fulfill({status:202,json:{retried:1,skipped:2}})});
 await page.goto('/#page=jobs');await page.getByRole('button',{name:'一键重试',exact:true}).click();await expect(page.getByText('已重新排队 1 项；跳过 2 项（额度、取消、重复或缺少配置）')).toBeVisible();expect(calls).toBe(1);
});

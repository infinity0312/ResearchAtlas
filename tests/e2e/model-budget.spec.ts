import {test,expect} from '@playwright/test';
import type {ModelBudget} from '../../web/api';

test('budget configuration is read-only until explicit save and preserves null caps',async({page})=>{
 let writes=0;
 let usageReads=0;
 let budget:ModelBudget={daily_tokens:null,task_tokens:12000,task_calls:null,timezone:'Asia/Shanghai'};
 await page.route('**/api/model-usage/budget',route=>{
  if(route.request().method()==='PUT'){
   writes++;
   const body=route.request().postDataJSON();
   expect(body).toEqual({daily_tokens:50000,task_tokens:12000,task_calls:null});
   budget={...budget,...body};
  }
  return route.fulfill({json:budget});
 });
 await page.route('**/api/model-usage',route=>{
  usageReads++;
  const {timezone,...caps}=budget;
  return route.fulfill({json:{day:'2026-09-30',timezone,budget:caps,totals:{attempts:3,settled_calls:1,pending_calls:1,unknown_calls:1,nonbillable_calls:0,known_tokens:writes?900:700,reserved_tokens:1100,committed_tokens:writes?2000:1800}}});
 });
 await page.goto('/#page=settings');
 const panel=page.locator('.model-budget-settings');
 await expect(panel.getByLabel('每日 Token 上限')).toHaveValue('');
 await expect(panel.getByLabel('每任务 Token 上限')).toHaveValue('12000');
 await expect(panel.getByLabel('每任务调用上限')).toHaveValue('');
 await expect(panel.getByRole('button',{name:'保存调用预算'})).toBeDisabled();
 expect(writes).toBe(0);
 await panel.getByLabel('每日 Token 上限').fill('50000');
 expect(writes).toBe(0);
 await panel.getByRole('button',{name:'保存调用预算'}).click();
 await expect(page.getByText('模型调用预算已保存',{exact:true})).toBeVisible();
 await expect(panel.getByRole('button',{name:'保存调用预算'})).toBeDisabled();
 expect(writes).toBe(1);
 await expect(panel.locator('.model-usage-totals>div').filter({hasText:'已报告 Token'})).toContainText('900');
 await expect(panel.locator('.model-usage-totals>div').filter({hasText:'待确认预留 Token'})).toContainText('1,100');
 await expect(panel.getByRole('status')).toContainText('今天的新模型请求将暂停');
 const reads=usageReads;
 await panel.getByRole('button',{name:'刷新用量'}).click();
 await expect.poll(()=>usageReads).toBeGreaterThan(reads);
 expect(writes).toBe(1);
 await expect(panel).toContainText('预留量为估计额度');
 await page.setViewportSize({width:390,height:844});
 await expect(panel).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBeTruthy();
});

test('budget load failure cannot submit invented defaults',async({page})=>{
 let writes=0;
 await page.route('**/api/model-usage/budget',route=>{if(route.request().method()==='PUT')writes++;return route.fulfill({status:503,json:{detail:'预算服务暂时不可用'}})});
 await page.route('**/api/model-usage',route=>route.fulfill({status:503,json:{detail:'用量服务暂时不可用'}}));
 await page.goto('/#page=settings');
 const panel=page.locator('.model-budget-settings');
 await expect(panel.getByRole('button',{name:'重试加载预算'})).toBeVisible({timeout:15000});
 await expect(panel.getByLabel('每日 Token 上限')).toHaveCount(0);
 await expect(panel.getByRole('button',{name:'保存调用预算'})).toHaveCount(0);
 expect(writes).toBe(0);
});

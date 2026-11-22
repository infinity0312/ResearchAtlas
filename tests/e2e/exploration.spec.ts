import {test,expect} from '@playwright/test';
test('exploration replaces sync and submits editable scope with all stages by default',async({page})=>{
 let payload:any;await page.route('**/api/exploration',async r=>{payload=r.request().postDataJSON();await r.fulfill({json:{job_id:'fixture-workflow'}})});
 await page.goto('/#page=overview');await page.getByRole('button',{name:'论文探索',exact:true}).click();
 const dialog=page.getByRole('dialog',{name:'论文探索'});await expect(dialog).toBeVisible();await expect(dialog.locator('.exploration-steps input:checked')).toHaveCount(4);
 await expect(page.getByLabel('每月目标篇数',{exact:true})).toHaveValue('3');await expect(page.getByLabel('每月抓取上限',{exact:true})).toHaveValue('6');
 await page.getByLabel('探索开始日期').fill('2025-01-01');await page.getByLabel('探索结束日期').fill('2025-02-28');await page.getByLabel('自定义 arXiv 检索式').check();await page.getByLabel('探索检索式').fill('abs:"molecular property prediction"');
 await page.getByRole('button',{name:'开始探索',exact:true}).click();await expect(dialog).toHaveCount(0);
 expect(payload.steps.sort()).toEqual(['analyze','fetch','search','statistics']);expect(payload.query).toBe('abs:"molecular property prediction"');expect(payload.target).toBe(3);expect(payload.threshold).toBe(70);
});
test('exploration supports statistics alone and mobile modal fits',async({page})=>{
 let payload:any;await page.route('**/api/exploration',async r=>{payload=r.request().postDataJSON();await r.fulfill({json:{job_id:'stats'}})});
 await page.setViewportSize({width:390,height:844});await page.goto('/#page=overview');await page.getByRole('button',{name:'论文探索',exact:true}).click();
 for(const name of ['检索','抓取','分析'])await page.locator('.exploration-steps label').filter({hasText:name}).getByRole('checkbox').uncheck();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await page.getByRole('button',{name:'开始探索',exact:true}).click();expect(payload.steps).toEqual(['statistics']);
});
test('checkpoint status exposes ranked choices and opens matching trend range',async({page})=>{
 await page.route('**/api/exploration/latest',r=>r.fulfill({json:[{id:'run1',status:'waiting',progress:70,message:'已达每日全文分析上限；将自动继续',payload:{start:'2025-01-01',end:'2025-03-31'},result:{catalog_count:200,ranked_count:200,analyzed:1,selected:[{id:'2609.00000',title:'Selected paper',month:'2025-01',score:91,reason:'验证充分且方法新颖',quote:'Exact abstract evidence',available:true}],trend_series_ids:['preset-0'],selection_rule:'质量优先'}}]}));
 await page.goto('/#page=overview');await expect(page.locator('.exploration-status')).toContainText('200 篇候选');await expect(page.locator('.exploration-status')).toContainText('等待额度');
 await page.getByText('查看月度精选与评分依据',{exact:true}).click();await expect(page.locator('.exploration-selection').first()).toContainText('91 分');
 await page.getByRole('button',{name:'查看探索范围趋势'}).click();await expect(page.getByLabel('趋势时间粒度')).toHaveValue('month');await expect(page.getByLabel('趋势开始时间')).toHaveValue('2025-01');
});

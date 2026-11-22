import {test,expect} from '@playwright/test';
test('dashboard renders real API responses without browser errors',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await expect(page.getByRole('heading',{name:'研究概览.'})).toBeVisible();
 await expect(page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true})).toBeVisible();
 await expect(page.locator('canvas').first()).toBeVisible();expect(errors).toEqual([]);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});
test('search, bookmark and reload retain user state',async({page,request})=>{
 await page.goto('/#page=papers&days=30');await page.getByRole('textbox',{name:'搜索标题或摘要'}).fill('Protein sequence');
 await expect(page.locator('.paper-row')).toHaveCount(1);
 await page.getByRole('button',{name:'收藏论文',exact:true}).click();await expect(page.getByRole('button',{name:'取消收藏',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'我的收藏',exact:true}).click();await expect(page.locator('main h1')).toHaveText('我的收藏.');await expect(page).toHaveURL(/#page=saved/);await expect(page.getByRole('button',{name:'Protein sequence representation learning',exact:true})).toBeVisible();
 await page.reload();await expect(page.getByRole('button',{name:'Protein sequence representation learning',exact:true})).toBeVisible();
 const target=page.getByRole('button',{name:'Protein sequence representation learning',exact:true});
 await page.locator('.paper-row').filter({has:target}).getByRole('button',{name:'取消收藏',exact:true}).click();await expect(target).toHaveCount(0);
 const state=await request.get('/api/paper?id=2609.00001');expect(state.ok()).toBeTruthy();expect((await state.json()).saved).toBe(false);
 await page.reload();await expect(target).toHaveCount(0);
});
test('paper evidence opens the matching page and modal closes by Escape',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 const dialog=page.getByRole('dialog',{name:'论文阅读'});await expect(dialog).toBeVisible();
 await dialog.getByRole('button',{name:/核对论文依据/}).click();
 const evidence=page.getByRole('dialog',{name:'论文依据'});await expect(evidence).toContainText('equivariant graph neural networks');
 await page.keyboard.press('Escape');await expect(evidence).not.toBeVisible();
 await page.keyboard.press('Escape');await expect(dialog).not.toBeVisible();
});
test('arbitrary research field can be created and edited',async({page})=>{
 await page.goto('/#page=settings');await page.getByRole('button',{name:'新增领域',exact:true}).click();
 const dialog=page.getByRole('dialog');await dialog.getByLabel('领域名称',{exact:true}).fill('天体物理测试');
 await dialog.getByLabel('arXiv 订阅规则',{exact:true}).fill('cat:astro-ph.GA');
 await dialog.getByLabel('初始小方向',{exact:true}).fill('星系演化，暗物质');
 await dialog.getByLabel('每天自动同步近期论文').uncheck();await dialog.getByRole('button',{name:'保存领域'}).click();
 await expect(dialog).not.toBeVisible();await expect(page.locator('.settings-domain').filter({hasText:'天体物理测试'})).toBeVisible();
});
test('missing API key produces actionable feedback',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 await page.getByRole('button',{name:'重新分析',exact:true}).click();await expect(page.getByRole('status')).toContainText('DeepSeek API Key');
});
test('mobile layouts do not overflow and navigation remains usable',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 const titles={overview:'研究概览.',papers:'发现论文.',map:'领域地图.',surveys:'综述知识库.',jobs:'后台任务.',settings:'工作台设置.'};
 for(const [route,title] of Object.entries(titles)){
  await page.goto('/#page='+route);await expect(page.locator('main h1')).toHaveText(title);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),route).toBeTruthy();
 }
 await page.getByRole('button',{name:'展开导航',exact:true}).click();await page.getByRole('button',{name:'研究概览',exact:true}).click();await expect(page.getByRole('heading',{name:'研究概览.'})).toBeVisible();
});

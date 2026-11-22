import {test,expect} from '@playwright/test';
test('node short label persists and resets',async({page,request})=>{
 await request.post('/api/tags/import-analysis',{headers:{'X-Atlas-Client':'1'}});
 await page.goto('/#page=map');await page.getByRole('button',{name:'切换标签筛选面板'}).click();await page.getByRole('button',{name:'选择当前列表',exact:true}).click();
 await expect(page.locator('.atlas-network')).toHaveAttribute('data-ready','true');
 await expect(page.locator('.paper-short-label')).toHaveText(['GNN']);
 await page.locator('.paper-legend > summary').click();await page.getByRole('button',{name:'编辑简称：Equivariant models for molecular prediction',exact:true}).click();
 await page.getByLabel('节点简称',{exact:true}).fill('EQNet');await page.locator('.graph-label-editor').getByRole('button',{name:'保存',exact:true}).click();
 await expect(page.locator('.paper-short-label')).toHaveText(['EQNet']);await page.reload();await expect(page.locator('.paper-short-label')).toHaveText(['EQNet']);
 await page.locator('.paper-legend > summary').click();await page.getByRole('button',{name:'编辑简称：Equivariant models for molecular prediction',exact:true}).click();await page.getByRole('button',{name:'恢复自动简称',exact:true}).click();await expect(page.locator('.paper-short-label')).toHaveText(['GNN']);
});
test('macro trends show remote counts, missing periods and editable query',async({page})=>{
 await page.route('**/api/trends/data?*',r=>r.fulfill({json:{series:[{id:'preset-0',name:'分子性质预测',query:'abs:"molecular property"',color:'#327c72',growth:30,points:[{period:'2023',count:100,fetched:'2026-09-26T00:00:00Z',partial:false},{period:'2024',count:null,fetched:null,partial:false},{period:'2025',count:130,fetched:'2026-09-26T00:00:00Z',partial:false}]}]}}));
 await page.goto('/#page=trends');await expect(page.getByRole('button',{name:'领域趋势',exact:true})).toBeVisible();await expect(page.getByRole('img',{name:'arXiv 小方向论文数量时间趋势图'})).toBeVisible();await expect(page.locator('.trend-value')).toContainText('130');
 await page.getByText('查看统计口径与原始计数',{exact:true}).click();await expect(page.locator('.trend-details')).toContainText('未获取');
 await page.getByRole('button',{name:'新增趋势方向',exact:true}).click();await page.getByLabel('趋势方向名称').fill('测试新方向');await page.getByLabel('趋势检索表达式').fill('ti:"test research"');await page.getByRole('button',{name:'保存方向',exact:true}).click();await expect(page.locator('.trend-choices')).toContainText('测试新方向');
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});
test('method matrix supports family granularity and manual correction',async({page})=>{
 await page.goto('/#page=map');await expect(page.getByLabel('方法统计粒度')).toHaveValue('families');
 await page.locator('.method-mappings > summary').click();const input=page.getByLabel('方法家族：等变 GNN');await input.fill('测试家族');await page.locator('.method-mappings form').filter({has:input}).getByRole('button',{name:'保存'}).click();await expect(page.locator('.matrix thead')).toContainText('测试家族');
 await page.getByLabel('方法统计粒度').selectOption('methods');await expect(page.locator('.matrix thead')).toContainText('等变 GNN');
});

test('dragging a paper reheats the simulation and moves its neighbours',async({page})=>{
 const tags=[{id:'force',name:'Force test',kind:'method',description:'',count:3,archived:false}];
 const papers=['a','b','c'].map(id=>({id,title:id,label:id.toUpperCase()}));
 await page.route('**/api/tags',r=>r.fulfill({json:tags}));
 await page.route('**/api/graph?*',r=>r.fulfill({json:{papers,tags,links:papers.map(p=>({paper_id:p.id,tag_id:'force',source:'manual'})),total:3,truncated:false}}));
 await page.goto('/#page=map');await page.getByRole('button',{name:'专注视图',exact:true}).click();await expect(page.locator('.atlas-network')).toHaveAttribute('data-ready','true');
 await page.emulateMedia({reducedMotion:'reduce'});await page.getByRole('button',{name:'重置视图',exact:true}).click();await expect(page.locator('.atlas-network')).toHaveAttribute('data-ready','true');
 const node=page.locator('[data-node-id="p:a"]'),other=page.locator('[data-node-id="p:b"]');
 const before=await other.getAttribute('transform');const dot=node.locator('.node-core');await dot.scrollIntoViewIfNeeded();const box=await dot.boundingBox();
 await page.mouse.move(box!.x+box!.width/2,box!.y+box!.height/2);await page.mouse.down();await page.mouse.move(box!.x+box!.width/2+100,box!.y+box!.height/2+65,{steps:12});
 await expect(other).not.toHaveAttribute('transform',before!);await page.mouse.up();await expect(page.getByRole('dialog',{name:'论文阅读'})).toHaveCount(0);
});

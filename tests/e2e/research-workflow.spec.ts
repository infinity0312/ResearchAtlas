import {test,expect} from '@playwright/test';

test('search rank reasons, date switch and version-scoped trace work on desktop and mobile',async({page})=>{
 await page.addInitScript(()=>sessionStorage.setItem('atlas.terminal.entered','1'));
 await page.setViewportSize({width:1440,height:1000});
 await page.goto('/#page=papers&days=0');
 await page.getByLabel('搜索标题或摘要').fill('equivariant');
 const row=page.locator('.paper-row').first();
 await expect(row).toContainText('题名命中 1/1');
 const response=page.waitForResponse(r=>r.url().includes('sort=recent')&&r.ok());
 await page.getByLabel('搜索排序').selectOption('recent');
 await response;
 await expect(page.locator('.paper-search-rank')).toHaveCount(0);
 const title=page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true});
 await title.click();
 const record=page.getByText('来源、研读记录与待核项',{exact:true});
 await record.click();
 await expect(page.locator('.paper-research-trace-body')).toContainText('TEST FIXTURE');
 await expect(page.locator('.paper-research-trace-body')).toContainText('待补全文报告');
 await page.setViewportSize({width:390,height:844});
 await expect(record).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('compares both positions under one criterion and opens the chosen source',async({page,request})=>{
 await page.addInitScript(()=>sessionStorage.setItem('atlas.terminal.entered','1'));
 const create=await request.post('/api/projects',{
  headers:{'X-Atlas-Client':'1'},data:{title:'对照验收项目',scenario:'route_review',owner:'隔离测试',
   question:'在相同工况下哪一条路线获得证据支持？',constraints:'测试范围',
   criteria:[{id:'protocol',label:'相同实验协议'}]},
 });
 expect(create.ok()).toBeTruthy();
 const project=await create.json();
 const details=await(await request.get('/api/projects/'+project.id)).json();
 const snapshot={paper_version:1,page:2,quote:'Source for an isolated layout and navigation test.'};
 const evidence=[
  {id:'left',analysis_id:1,paper_id:'2609.00000',criterion_id:'protocol',stance:'supports',
   context:'使用同一验证划分',snapshot:{...snapshot,paper_title:'夹具论文 A',claim_text:'在验证划分 A 的实验中表现稳定'},
   health:{eligible:true,issues:[],quality:null,latest_analysis_id:1}},
  {id:'right',analysis_id:2,paper_id:'2609.00001',criterion_id:'protocol',stance:'contradicts',
   context:'测试协议不同，需要再核查',snapshot:{...snapshot,paper_title:'夹具论文 B',claim_text:'在划分 B 的实验中表现下降'},
   health:{eligible:false,issues:['需要核对来源'],quality:null,latest_analysis_id:2}},
 ];
 await page.route('**/api/projects/'+project.id,r=>r.fulfill({json:{...details,evidence}}));
 await page.goto('/#page=projects&project_id='+project.id);
 await page.getByRole('navigation',{name:'项目章节'}).getByRole('button',{name:'核对证据',exact:true}).click();
 await page.getByText('并排核对两篇论文的依据',{exact:true}).click();
 const comparison=page.locator('.project-evidence-comparison');
 await expect(comparison).toContainText('支持 · 当前有效');
 await expect(comparison).toContainText('反对 · 待复核');
 await expect(comparison).toContainText('测试协议不同，需要再核查');
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await comparison.getByRole('button',{name:'核对原文与绑定版本'}).last().click();
 await expect(page.locator('[data-evidence-id="right"]')).toHaveClass(/is-selected/);
});

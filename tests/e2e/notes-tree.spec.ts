import {test,expect} from '@playwright/test';
test('Markdown notes persist, restore drafts, link and render math safely',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.request.post('/api/notes',{headers:{'X-Atlas-Client':'1'},data:{title:'目标笔记',series:'教程',content:'# Destination'}});
 await page.goto('/#page=notes');await page.getByRole('button',{name:'新建笔记',exact:true}).click();
 await page.getByLabel('笔记标题',{exact:true}).fill('我的方法笔记');await page.getByRole('combobox',{name:'笔记系列',exact:true}).fill('教程');
 const body='# 数学笔记\n\n$$\\rho_{\\mathrm{init}}(r)=r^2$$\n\n- [x] 核对定义\n\n|符号|解释|\n|---|---|\n|r|距离|\n\n[[目标笔记]]\n\n<script>window.pwned=1</script>\n\n[bad](javascript:alert(1))';
 await page.locator('.cm-content').fill(body);await expect(page.locator('.note-preview .katex')).toHaveCount(1);await expect(page.locator('.note-preview table')).toBeVisible();
 await expect(page.locator('.note-preview a[href^="javascript:"]')).toHaveCount(0);await expect(page.locator('.note-preview script')).toHaveCount(0);
 await page.getByRole('button',{name:'保存',exact:true}).click();await expect(page.locator('.note-toolbar [role=status]')).toHaveText('已保存');
 await page.reload();await page.locator('.notes-file-list').getByRole('button',{name:/我的方法笔记/}).click();await page.getByRole('button',{name:'双栏',exact:true}).click();await expect(page.locator('.cm-content')).toContainText('核对定义');
 await page.locator('.cm-content').fill(body+'\n\n未保存草稿');await page.reload();await page.locator('.notes-file-list').getByRole('button',{name:/我的方法笔记/}).click();await page.getByRole('button',{name:'双栏',exact:true}).click();await expect(page.locator('.cm-content')).toContainText('未保存草稿');
 await page.getByRole('button',{name:'保存',exact:true}).click();await expect(page.locator('.note-toolbar [role=status]')).toHaveText('已保存');
 await page.locator('.note-preview').getByRole('button',{name:'目标笔记',exact:true}).click();await expect(page.getByLabel('笔记标题',{exact:true})).toHaveValue('目标笔记');await expect(page.locator('.note-backlinks')).toContainText('我的方法笔记');
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();expect(errors).toEqual([]);
});
test('hierarchy displays published topic branches and unclassified papers',async({page})=>{
 await page.goto('/#page=map');await expect(page.getByRole('heading',{name:'研究分类树'})).toBeVisible();
 await expect(page.locator('.hierarchy-panel')).toContainText('手动预设');
 await expect(page.locator('.tree-topic.pending').first()).toContainText('待分析');
 await page.locator('.tree-paper').filter({hasText:'Equivariant models for molecular prediction'}).click();
 await expect(page.getByRole('dialog',{name:'论文阅读'})).toBeVisible();await expect(page.getByRole('button',{name:'解析原文',exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'论文摘要',exact:true}).click();await expect(page.locator('.abstract-editorial')).toContainText('原文摘要');
});
test('method tutorial exposes equations, symbol definitions, derivation and evidence',async({page})=>{
 await page.route('**/api/lessons?*',r=>r.fulfill({json:[{claim_index:0,result:{title:'数学讲解测试',motivation:'研究动机',prerequisites:'适用假设',symbols:[{symbol:'\\rho_{\\mathrm{init}}',meaning:'初始密度',domain_units:'电子数/体积'}],equations:[{latex:'\\rho=\\rho_{\\mathrm{init}}+\\rho_{\\mathrm{env}}',explanation:'密度分解公式',origin:'teaching'}],derivation:'由线性叠加得到 \\(x^2\\)。',example:'一个算例',conclusions:'结论分析',limitations:'适用边界',sources:[{page:1,quote:'equivariant graph neural networks'}]}}]}));
 await page.goto('/#page=papers');await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 await page.locator('.lesson-expansion > summary').click();await expect(page.locator('.symbol-scroll')).toContainText('电子数/体积');
 await expect(page.locator('.lesson-body .katex')).toHaveCount(3);await expect(page.locator('.lesson-body')).toContainText('结论分析');await expect(page.locator('.lesson-equation')).toContainText('教学补充');
});

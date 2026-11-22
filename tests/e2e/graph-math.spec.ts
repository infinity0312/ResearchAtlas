import {test,expect} from '@playwright/test';
test('math renders inline, display, matrix and align without executing links',async({page})=>{
 await page.goto('/#page=papers');await page.getByRole('button',{name:'Protein sequence representation learning',exact:true}).click();
 const dialog=page.getByRole('dialog',{name:'论文阅读'});await dialog.getByRole('button',{name:'论文摘要',exact:true}).click();
 await expect(dialog.locator('.katex').first()).toBeVisible();expect(await dialog.locator('.katex').count()).toBeGreaterThanOrEqual(5);
 expect(await dialog.locator('.katex-display').count()).toBeGreaterThanOrEqual(3);
 await expect(dialog.locator('a[href^="javascript:"]')).toHaveCount(0);
 await expect(dialog.locator('.abstract-prose')).toContainText('badcommand');
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});
test('tags can be edited, attached, filtered and archived through UI',async({page})=>{
 await page.goto('/#page=map');await page.getByRole('button',{name:'新建标签',exact:true}).click();
 let dialog=page.getByRole('dialog',{name:'新建标签'});await dialog.getByLabel('标签名称',{exact:true}).fill('图谱测试问题');await dialog.getByLabel('标签类型',{exact:true}).selectOption('problem');await dialog.getByRole('button',{name:'保存标签'}).click();await expect(dialog).not.toBeVisible();
 await page.getByRole('button',{name:'发现论文',exact:true}).click();await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 dialog=page.getByRole('dialog',{name:'论文阅读'});await dialog.locator('.reader-tags > summary').click();await dialog.getByLabel('选择文献标签').selectOption({label:'解决的问题 · 图谱测试问题'});await dialog.getByRole('button',{name:'添加标签',exact:true}).click();await expect(dialog.locator('.tag-cloud')).toContainText('图谱测试问题');await dialog.getByRole('button',{name:'关闭',exact:true}).click();
 await page.getByRole('button',{name:'领域地图',exact:true}).click();await page.getByRole('button',{name:'切换标签筛选面板'}).click();await page.getByRole('button',{name:'清空选择',exact:true}).click();await page.getByRole('checkbox',{name:/图谱测试问题/}).check();await expect(page.locator('.graph-toolbar')).toContainText('1 篇文献');await expect(page.locator('.relation-canvas > svg')).toBeVisible();
 await page.getByRole('button',{name:'编辑标签 图谱测试问题',exact:true}).click();dialog=page.getByRole('dialog',{name:'编辑标签'});await dialog.getByLabel('标签名称',{exact:true}).fill('图谱问题已改名');await dialog.getByRole('button',{name:'保存标签'}).click();await expect(page.getByRole('checkbox',{name:/图谱问题已改名/})).toBeChecked();
 await page.getByRole('button',{name:'清空选择',exact:true}).click();await expect(page.locator('.graph-toolbar')).toContainText('0 篇文献');await expect(page.locator('.relation-canvas')).toHaveCount(0);
 await page.getByRole('button',{name:'归档标签 图谱问题已改名',exact:true}).click();await expect(page.getByRole('checkbox',{name:/图谱问题已改名/})).toHaveCount(0);await page.getByLabel('查看已归档标签').check();await page.getByRole('button',{name:'恢复标签 图谱问题已改名',exact:true}).click();await expect(page.getByRole('checkbox',{name:/图谱问题已改名/})).toBeVisible();
});

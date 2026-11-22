import {test,expect} from '@playwright/test';
test('manual PDF import opens the local reader and reuses duplicate content',async({page,request})=>{
 const pdf=await request.get('/api/paper/pdf?id=2609.00000&version=1');expect(pdf.ok()).toBeTruthy();const buffer=await pdf.body();
 await page.goto('/#page=overview');await page.getByRole('button',{name:'导入文献',exact:true}).click();
 await page.getByLabel('上传论文 PDF').setInputFiles({name:'manual-paper.pdf',mimeType:'application/pdf',buffer});
 await page.getByLabel('导入论文标题').fill('Manual import research');await page.getByLabel('导入发表日期').fill('2001-02-03');await page.getByLabel('收录后进行全文分析').uncheck();
 await page.getByRole('button',{name:'收录文献',exact:true}).click();await expect(page.getByRole('status')).toContainText('文献已收录');await page.screenshot({path:'docs/manual-import-success.png'});
 await page.getByRole('button',{name:'打开文献',exact:true}).click();const dialog=page.getByRole('dialog',{name:'论文阅读'});await expect(dialog).toContainText('Manual import research');await expect(dialog).toContainText('本地导入');
 await page.getByRole('button',{name:'原始 PDF',exact:true}).click();await expect(page.getByRole('img',{name:'原始论文 PDF · 第 1 页',exact:true})).toBeVisible();
 const duplicate=await request.post('/api/paper/import',{headers:{'X-Atlas-Client':'1'},multipart:{domain_id:'molecules',analyze:'false',file:{name:'same.pdf',mimeType:'application/pdf',buffer}}});expect(duplicate.status()).toBe(201);expect((await duplicate.json()).duplicate).toBeTruthy();
});

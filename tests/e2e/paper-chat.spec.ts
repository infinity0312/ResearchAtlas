import {test,expect} from '@playwright/test';
test('paper questions render math, persist history and navigate original evidence',async({page})=>{
 const turns:any[]=[];
 await page.route('**/api/paper/chat?*',async route=>{
  if(route.request().method()==='POST'){
   const body=route.request().postDataJSON();turns.push({id:body.request_id,question:body.question,answer:'量化误差为 $e=x-\\hat{x}$。\n\n- 解释符号\n- 分析结论',version:1,status:'done',scope:'已解析全文',model:'test',sources:[{index:0,page:1,text:'Original method evidence'}]});
   await route.fulfill({json:turns.at(-1)});
  }else await route.fulfill({json:turns});
 });
 await page.goto('/#page=papers');await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 await page.getByRole('button',{name:'提问记录',exact:true}).click();
 await page.getByLabel('针对本文提问').fill('请解释量化误差');await page.getByRole('button',{name:'发送问题',exact:true}).click();
 await expect(page.locator('.chat-answer .katex')).toHaveCount(1);await expect(page.locator('.chat-answer li')).toHaveCount(2);
 await page.locator('.chat-sources summary').click();await expect(page.locator('.chat-sources')).toContainText('Original method evidence');
 await page.getByRole('button',{name:'在 PDF 中查看',exact:true}).click();await expect(page.locator('.pdf-reading')).toBeVisible();
 await page.getByRole('button',{name:'提问记录',exact:true}).click();await expect(page.locator('.chat-question')).toContainText('请解释量化误差');
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

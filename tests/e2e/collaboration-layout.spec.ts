import {test,expect} from '@playwright/test';
test('reader collaboration keeps gutters and expanded form within narrow and wide dialogs',async({page})=>{
 await page.addInitScript(()=>sessionStorage.setItem('atlas.terminal.entered','1'));
 await page.goto('/#page=papers&days=0');
 await page.getByRole('button',{name:'打开论文',exact:true}).first().click();
 await page.getByRole('button',{name:'深度协作',exact:true}).click();
 await expect(page.locator('.detail>.collaboration-panel')).toBeVisible();
 await page.getByRole('button',{name:'创建协作任务',exact:true}).click();
 for(const width of [390,768,1440]){
  await page.setViewportSize({width,height:900});
  await expect(page.getByLabel('协作任务标题')).toBeVisible();
  const sizes=await page.locator('.detail>.collaboration-panel').evaluate(el=>{
   const r=el.getBoundingClientRect(),h=el.querySelector('h3')!.getBoundingClientRect();
   return {gutter:h.left-r.left,overflow:el.scrollWidth-el.clientWidth,form:el.querySelector('form')!.scrollWidth-el.querySelector('form')!.clientWidth};
  });
  expect(sizes.gutter).toBeGreaterThanOrEqual(18);expect(sizes.overflow).toBeLessThanOrEqual(1);expect(sizes.form).toBeLessThanOrEqual(1);
 }
});

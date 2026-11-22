import {test,expect} from '@playwright/test';

test('a late highlight creation from v1 cannot enter the visible v2 annotation set',async({page})=>{
 let currentVersion=1;
 let releasePost!:()=>void,postStarted!:()=>void,v2Loaded!:()=>void;
 const heldPost=new Promise<void>(resolve=>releasePost=resolve);
 const pendingPost=new Promise<void>(resolve=>postStarted=resolve);
 const v2Marks=new Promise<void>(resolve=>v2Loaded=resolve);
 let posted:Record<string,unknown>|null=null;
 await page.route('**/api/paper?*',async route=>{
  const response=await route.fetch(),paper=await response.json();paper.pdf_version=currentVersion;
  await route.fulfill({response,json:paper});
 });
 await page.route('**/api/paper/state?*',route=>route.fulfill({json:{ok:true}}));
 await page.route('**/api/paper/highlights?*',async route=>{
  const version=new URL(route.request().url()).searchParams.get('version');
  if(route.request().method()==='POST'){
   posted=route.request().postDataJSON();postStarted();await heldPost;
   await route.fulfill({json:{id:'late-v1-highlight',...posted,note:''}});return;
  }
  await route.fulfill({json:[]});if(version==='2')v2Loaded();
 });
 await page.route('**/api/paper/pdf?*',async route=>{
  const original=new URL(route.request().url());original.searchParams.set('version','1');
  const response=await route.fetch({url:original.toString()});await route.fulfill({response});
 });
 await page.route('**/api/paper/chat?*',route=>route.fulfill({json:[{id:'v2-citation',version:2,
  question:'当前版本的问题',answer:'当前版本回答',status:'done',scope:'全文',model:'fixture',error:'',
  sources:[{index:1,page:1,text:'Version two source context.'}]}]}));
 try{
  await page.goto('/#page=papers');
  await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
  await page.getByRole('button',{name:'原始 PDF',exact:true}).click();
  const text=page.locator('.textLayer span').filter({hasText:'Selectable original paper text.'});
  await expect(text).toBeVisible();
  // Select rendered PDF text and use the same visible annotation action as the user.
  await text.evaluate(el=>{const range=document.createRange();range.selectNodeContents(el);
   window.getSelection()?.removeAllRanges();window.getSelection()?.addRange(range);
   document.dispatchEvent(new PointerEvent('pointerup',{bubbles:true}));
  });
  await page.getByRole('button',{name:'高亮标注',exact:true}).click();await pendingPost;
  expect(posted).toMatchObject({version:1,page:1,quote:'Selectable original paper text.'});
  currentVersion=2;
  const refreshed=page.waitForResponse(async response=>new URL(response.url()).pathname==='/api/paper'&&(await response.json()).pdf_version===2);
  await page.getByRole('button',{name:/^(收藏|已收藏)$/}).click();await refreshed;
  await page.getByRole('button',{name:'提问记录',exact:true}).click();
  await page.locator('.chat-sources>summary').click();
  await page.locator('.chat-sources').getByRole('button',{name:'在 PDF 中查看',exact:true}).click();
  await v2Marks;
  await expect(page.locator('.pdf-reading .notice')).toContainText('v2');
  await expect(page.getByRole('button',{name:'标注 0',exact:true})).toBeVisible();
  const lateResponse=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/paper/highlights'&&response.request().method()==='POST');
  releasePost();await lateResponse;
  await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
  await expect(page.getByRole('button',{name:'标注 0',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'高亮：Selectable original paper text.',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'标注 0',exact:true}).click();
  await expect(page.locator('.pdf-mark-list article')).toHaveCount(0);
 }finally{releasePost()}
});

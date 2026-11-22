import {test,expect} from '@playwright/test';

async function openEvidence(page:import('@playwright/test').Page){
 await page.route('**/api/paper?*',async route=>{
  const response=await route.fetch(),paper=await response.json();
  if(paper.id==='2609.00000')paper.analysis.result.claims.push({kind:'contribution',basis:'author',text:'核查布局专用来源夹具',page:2,quote:'Fixture quotation for page navigation, not a scientific finding.'});
  await route.fulfill({response,json:paper});
 });
 await page.goto('/#page=papers');
 await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 const trigger=page.getByRole('button',{name:/核查布局专用来源夹具/});
 await trigger.click();
 return {trigger,sign:page.locator('.atlas-source-sign:visible')};
}

test('source checking keeps one PDF instance and returns to the selected analysis context',async({page})=>{
 await page.setViewportSize({width:1440,height:900});
 const pdfRequests:string[]=[];
 page.on('request',request=>{if(new URL(request.url()).pathname==='/api/paper/pdf')pdfRequests.push(request.url())});
 const {trigger,sign}=await openEvidence(page);
 await expect(sign).toContainText('第 2 页');await expect(sign).toContainText('论文 v1');
 await expect(sign).toContainText('尚未执行逐句匹配');
 await sign.getByRole('button',{name:'在 PDF 中查看此页'}).click();
 await expect(page.getByLabel('PDF 页码',{exact:true})).toHaveValue('2');
 await expect(page.getByRole('img',{name:'原始论文 PDF · 第 2 页',exact:true})).toBeVisible();
 expect(pdfRequests.length).toBeGreaterThan(0);
 expect(pdfRequests.every(url=>{const q=new URL(url).searchParams;return q.get('id')==='2609.00000'&&q.get('version')==='1'})).toBeTruthy();
 const originalRequestCount=pdfRequests.length;
 await expect(page.locator('.pdf-reading .atlas-source-sign')).toBeVisible();
 await expect(page.locator('.pdf-reader')).toHaveCount(1);
 await page.getByRole('button',{name:'PDF 放大',exact:true}).click();
 await page.locator('.pdf-reading .atlas-return-context').click();
 await expect(trigger).toBeFocused();await expect(trigger).toBeInViewport();
 await expect(page.locator('.analysis-content')).toBeVisible();
 await page.getByRole('button',{name:'原始 PDF',exact:true}).click();
 await expect(page.getByRole('button',{name:'适合宽度 · 125%',exact:true})).toBeVisible();
 await expect(page.locator('.pdf-reader')).toHaveCount(1);
 expect(pdfRequests).toHaveLength(originalRequestCount);
 // Revisiting preserves manual position; explicit locate returns to the cited page.
 await page.getByLabel('PDF 页码',{exact:true}).fill('1');
 await page.locator('.pdf-reading .atlas-return-context').click();
 await page.locator('.atlas-source-sign:visible').getByRole('button',{name:'返回 PDF 核查'}).click();
 await expect(page.getByLabel('PDF 页码',{exact:true})).toHaveValue('1');
 await page.locator('.pdf-reading').getByRole('button',{name:'定位引用页',exact:true}).click();
 await expect(page.getByLabel('PDF 页码',{exact:true})).toHaveValue('2');
 expect(pdfRequests).toHaveLength(originalRequestCount);
});

test('narrow source checking switches between original and evidence without squeezing two columns',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 const {sign}=await openEvidence(page);
 await sign.getByRole('button',{name:'在 PDF 中查看此页'}).click();
 const switcher=page.getByRole('group',{name:'核查视图'});
 await expect(page.locator('.atlas-pdf-main')).toBeVisible();
 await switcher.getByRole('button',{name:'依据',exact:true}).click();
 await expect(page.locator('.atlas-pdf-main')).toBeHidden();
 await expect(page.getByRole('dialog',{name:'论文依据',exact:true})).toBeVisible();
 await page.getByRole('dialog',{name:'论文依据',exact:true}).press('Escape');
 await expect(page.getByLabel('PDF 页码',{exact:true})).toHaveValue('2');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
 await switcher.getByRole('button',{name:'依据',exact:true}).click();
 await page.setViewportSize({width:1440,height:900});
 await expect(page.locator('.atlas-pdf-main')).toBeVisible();
 await page.locator('.pdf-page-host').hover();
 await page.mouse.wheel(0,-5000);
 await expect(page.getByLabel('PDF 页码',{exact:true})).toHaveValue('1');
});

test('reverse tab stays in visible reader controls after the persistent PDF is hidden',async({page})=>{
 await openEvidence(page);
 await page.locator('.atlas-source-sign:visible').getByRole('button',{name:'在 PDF 中查看此页'}).click();
 await expect(page.getByLabel('PDF 页码',{exact:true})).toHaveValue('2');
 await page.getByRole('button',{name:'论文摘要',exact:true}).click();
 const dialog=page.getByRole('dialog',{name:'论文阅读'});
 await dialog.locator('.modal-head').getByRole('button',{name:'关闭',exact:true}).focus();
 for(let i=0;i<12;i++){
  await page.keyboard.press('Shift+Tab');
  expect(await dialog.evaluate(el=>{const active=document.activeElement as HTMLElement|null;return !!active&&el.contains(active)&&!active.closest('[hidden],[inert]')&&active.getClientRects().length>0&&!active.closest('.pdf-reading')})).toBeTruthy();
 }
 await expect(page.locator('.pdf-reader')).toHaveCount(1);
 await expect(page.locator('.pdf-reading')).toBeHidden();
});

test('method evidence close restores its trigger and PDF close keeps the current reading mode',async({page})=>{
 await page.goto('/#page=papers');
 await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 const trigger=page.locator('.method-card-heading .evidence-button').first();
 await trigger.click();
 await page.getByRole('button',{name:'关闭论文依据',exact:true}).click();
 await expect(trigger).toBeFocused();await expect(trigger).toBeInViewport();
 await trigger.click();
 await page.locator('.atlas-source-sign:visible').getByRole('button',{name:'在 PDF 中查看此页'}).click();
 await page.getByLabel('PDF 页码',{exact:true}).fill('2');
 await page.getByRole('img',{name:'原始论文 PDF · 第 2 页',exact:true}).waitFor();
 await expect(page.getByLabel('PDF 页码',{exact:true})).toHaveValue('2');
 await page.locator('.pdf-reading').getByRole('button',{name:'关闭论文依据',exact:true}).click();
 await expect(page.locator('.detail')).toHaveAttribute('data-reading-mode','pdf');
 await expect(page.getByLabel('PDF 页码',{exact:true})).toHaveValue('2');
 await expect(page.getByLabel('PDF 页码',{exact:true})).toBeFocused();
 await expect(page.locator('.atlas-source-sign')).toHaveCount(0);
});

test('local paper abstract never links a local identifier to arXiv',async({page})=>{
 await page.route('**/api/paper?*',async route=>{
  const response=await route.fetch(),paper=await response.json();paper.id='local-reader-fixture';
  await route.fulfill({response,json:paper});
 });
 await page.goto('/#page=papers');
 await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 await page.getByRole('button',{name:'论文摘要',exact:true}).click();
 await expect(page.locator('.abstract-prose')).toBeVisible();
 await expect(page.getByRole('dialog',{name:'论文阅读'}).locator('a[href*="arxiv.org/abs/local-"]')).toHaveCount(0);
});

test('chapter position and selected source share context without moving the selected passage',async({page})=>{
 await page.setViewportSize({width:1440,height:900});
 const {trigger}=await openEvidence(page);
 await expect(trigger).toHaveClass(/atlas-selected-claim/);
 await expect(page.locator('.atlas-current-source')).toContainText('第 2 页');
 await expect(page.locator('.atlas-reading-layout>.atlas-source-sign')).toBeVisible();
 await page.getByRole('navigation',{name:'阅读章节'}).getByRole('button',{name:'局限',exact:true}).click();
 await expect(page.getByRole('navigation',{name:'阅读章节'}).getByRole('button',{name:'局限',exact:true})).toHaveAttribute('aria-current','location');
 await expect(page.locator('.atlas-reading-bar')).toHaveClass(/is-compact/);
 await expect(page.locator('.atlas-current-source')).toContainText('来源');
 await page.locator('.atlas-source-sign').getByRole('button',{name:'关闭论文依据',exact:true}).click();
 await expect(trigger).toBeFocused();await expect(trigger).toBeInViewport();
});

test('mobile source sheet traps focus and escape returns to the selected claim',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 const {trigger}=await openEvidence(page);
 const sheet=page.getByRole('dialog',{name:'论文依据',exact:true});
 await expect(sheet).toBeVisible();
 for(let i=0;i<12;i++){await page.keyboard.press('Tab');expect(await sheet.evaluate(el=>el.contains(document.activeElement))).toBeTruthy()}
 await sheet.press('Escape');
 await expect(sheet).toHaveCount(0);await expect(trigger).toBeFocused();await expect(trigger).toBeInViewport();
});

test('chat citation opens its current PDF version without inheriting an earlier analysis source',async({page})=>{
 await page.route('**/api/paper?*',async route=>{
  const response=await route.fetch(),paper=await response.json();paper.pdf_version=2;
  paper.analysis.result.claims.push({kind:'contribution',basis:'author',text:'旧分析来源上下文',page:1,quote:'Old analysis quotation.'});
  await route.fulfill({response,json:paper});
 });
 await page.route('**/api/paper/chat?*',route=>route.fulfill({json:[{id:'chat-version-2',version:2,question:'当前版本的问题',answer:'当前版本的回答',status:'done',error:'',scope:'全文',model:'fixture',sources:[{index:1,page:2,text:'Current chat version source.'}]}]}));
 await page.route('**/api/paper/pdf?*',async route=>{
  const original=new URL(route.request().url());original.searchParams.set('version','1');
  const response=await route.fetch({url:original.toString()});await route.fulfill({response});
 });
 await page.goto('/#page=papers');
 await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 await page.getByRole('button',{name:/旧分析来源上下文/}).click();
 await expect(page.locator('.atlas-source-sign:visible')).toContainText('论文 v1');
 await page.getByRole('button',{name:'提问记录',exact:true}).click();
 await page.locator('.chat-sources>summary').click();
 const request=page.waitForRequest(r=>{const url=new URL(r.url());return url.pathname==='/api/paper/pdf'&&url.searchParams.get('version')==='2'});
 await page.locator('.chat-sources').getByRole('button',{name:'在 PDF 中查看',exact:true}).click();await request;
 await expect(page.getByLabel('PDF 页码',{exact:true})).toHaveValue('2');
 await expect(page.locator('.atlas-source-sign')).toHaveCount(0);
 await expect(page.locator('.pdf-reading .notice')).toContainText('v2');
});

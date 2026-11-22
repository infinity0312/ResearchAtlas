import {test,expect} from '@playwright/test';
import {legacyMath} from '../../web/legacyMath';

test('plain Greek equations are rendered without touching existing math and code',()=>{
 expect(legacyMath('扰动 σp = min(0.1σ, 0.5)。')).toContain('\\(\\sigma_{p} = \\min(0.1\\sigma , 0.5)\\)');
 expect(legacyMath('$σp = min(0.1σ, 0.5)$ `σp = min(0.1σ, 0.5)`')).toBe('$σp = min(0.1σ, 0.5)$ `σp = min(0.1σ, 0.5)`');
});

test('select analysis, ask with quote, delete and restore history',async({page})=>{
 let turns:any[]=[];let payload:any;
 await page.route('**/api/paper?*',async route=>{const response=await route.fetch();const p=await response.json();p.analysis.result.summary='扰动 σp = min(0.1σ, 0.5)。这是需要解释的核心方法。';await route.fulfill({json:p})});
 await page.route('**/api/paper/chat**',async route=>{
  const req=route.request(),url=new URL(req.url());
  if(req.method()==='DELETE'){turns[0].deleted=true;await route.fulfill({json:{ok:true}});return}
  if(url.pathname.endsWith('/restore')){turns[0].deleted=false;await route.fulfill({json:{ok:true}});return}
  if(req.method()==='POST'){payload=req.postDataJSON();turns.push({...payload,id:payload.request_id,version:1,answer:'这是公式的解释。',scope:'原文选段',status:'done',sources:[],deleted:false});await route.fulfill({json:turns.at(-1)});return}
  await route.fulfill({json:turns.filter(t=>t.deleted===(url.searchParams.get('deleted')==='true'))});
 });
 await page.goto('/#page=papers');await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 await expect(page.locator('.analysis-summary .katex')).toHaveCount(1);
 await page.locator('.analysis-summary').evaluate(el=>{const r=document.createRange();r.selectNodeContents(el.querySelector('p')!);const s=window.getSelection()!;s.removeAllRanges();s.addRange(r);document.dispatchEvent(new PointerEvent('pointerup'))});
 await expect(page.getByRole('toolbar',{name:'选中文本操作'})).toHaveCSS('position','fixed');
 await page.getByRole('button',{name:'就此提问',exact:true}).click();
 await expect(page.locator('.chat-quote-draft')).toContainText('这是需要解释的核心方法');
 await page.getByLabel('针对本文提问').fill('推导这个公式');await page.getByRole('button',{name:'发送问题'}).click();
 await expect(page.locator('.chat-answer')).toContainText('这是公式的解释');
 expect(payload.selected_text).toContain('\\sigma');expect(payload.selected_text.match(/核心方法/g)).toHaveLength(1);
 await expect(page.getByLabel('继续提问')).toBeVisible();
 await page.getByRole('button',{name:'删除提问记录',exact:true}).click();await expect(page.locator('.chat-turns article')).toHaveCount(0);
 await page.getByRole('button',{name:'已删除记录',exact:true}).click();await expect(page.locator('.chat-turns article')).toHaveCount(1);
 await page.getByRole('button',{name:'恢复提问记录',exact:true}).click();await page.getByRole('button',{name:'返回对话',exact:true}).click();await expect(page.locator('.chat-turns article')).toHaveCount(1);
 await page.screenshot({path:'docs/selection-chat-verified.png'});
});

test('PDF text layer is selectable and supplies the page number',async({page})=>{
 await page.goto('/#page=papers');await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 await page.getByRole('button',{name:'原始 PDF',exact:true}).click();
 const text=page.locator('.textLayer span').filter({hasText:'Selectable original paper text.'});await expect(text).toHaveCount(1);
 await text.evaluate(el=>{const r=document.createRange();r.selectNodeContents(el);const s=window.getSelection()!;s.removeAllRanges();s.addRange(r);document.dispatchEvent(new PointerEvent('pointerup'))});
 await page.getByRole('button',{name:'就此提问'}).click();await expect(page.locator('.chat-quote-draft')).toContainText('第 1 页');await expect(page.locator('.chat-quote-draft')).toContainText('Selectable original paper text.');
});

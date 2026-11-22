import {test,expect} from '@playwright/test';
import {legacyMath} from '../../web/legacyMath';

test('legacy mathematical notation is displayed without altering existing TeX or code',()=>{
 expect(legacyMath('ρ_init + ρ_env; E_Fermi; N^4')).toContain('\\rho_{\\mathrm{init}}');
 expect(legacyMath('$E_Fermi$ and \\(ρ_init\\)')).toBe('$E_Fermi$ and \\(ρ_init\\)');
 expect(legacyMath('`ρ_init` file_name https://example.com/N^4')).toBe('`ρ_init` file_name https://example.com/N^4');
 expect(legacyMath('ρinit(r) + rhoenv(r)')).toBe('\\(\\rho_{\\mathrm{init}}(\\mathbf{r})\\) + \\(\\rho_{\\mathrm{env}}(\\mathbf{r})\\)');
});
test('existing analysis renders bare math and related papers open a clean reader',async({page})=>{
 // Exercise legacy notation even when the editing suite already saved a new summary.
 await page.route('**/api/paper?*',async route=>{
  const response=await route.fetch();const paper=await response.json();
  if(paper.id==='2609.00000')paper.analysis.result.summary='这是浏览器测试数据，不是真实模型分析。ρ_init 与 ρ_env 用于测试旧记法。';
  await route.fulfill({response,json:paper});
 });
 await page.goto('/#page=papers');await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 const dialog=page.getByRole('dialog',{name:'论文阅读'});
 await expect(dialog.locator('.analysis-summary .katex')).toHaveCount(2);
 await dialog.getByRole('button',{name:'相关文献',exact:true}).click();await expect(dialog.locator('.related-card').first()).toBeVisible();
 await dialog.locator('.related-card').first().click();await expect(page.getByRole('dialog',{name:'论文阅读'})).toBeVisible();await expect(page.locator('.detail-heading h2')).not.toHaveText('Equivariant models for molecular prediction');
 await page.getByRole('button',{name:'原始 PDF',exact:true}).click();await expect(page.getByRole('heading',{name:'此论文尚无本地 PDF'})).toBeVisible();
});
test('hover preview remains available while moving to its details card',async({page})=>{
 const tag={id:'hover-test',name:'Motion test',kind:'method',description:'Hover details',count:1,archived:false};
 await page.route('**/api/tags',r=>r.fulfill({json:[tag]}));await page.route('**/api/tags?*',r=>r.fulfill({json:[tag]}));
 await page.route('**/api/graph?*',r=>r.fulfill({json:{papers:[{id:'2609.00000',title:'Paper'}],tags:[tag],links:[{paper_id:'2609.00000',tag_id:tag.id,source:'manual'}],total:1,truncated:false}}));
 await page.goto('/#page=map');await expect(page.locator('.atlas-network')).toHaveAttribute('data-ready','true');
 const node=page.locator('[data-node-id="p:2609.00000"]');await node.hover();await expect(page.locator('.network-inspector')).toContainText('Motion test');
 await page.locator('.network-inspector').hover();await expect(page.locator('.network-inspector')).toHaveAttribute('aria-hidden','false');
 const duration=await page.locator('.network-inspector').evaluate(el=>getComputedStyle(el).transitionDuration);expect(duration).not.toBe('0s');
 await page.getByRole('heading',{name:'文献关系图谱',exact:true}).hover();await expect(page.locator('.network-inspector')).toHaveCount(0);
 await page.emulateMedia({reducedMotion:'reduce'});await node.focus();await expect(page.locator('.network-inspector')).toBeVisible();expect(await page.locator('.network-inspector').evaluate(el=>getComputedStyle(el).transitionDuration)).toBe('0s');
});
test('built-in PDF reader renders and navigates without a browser PDF plugin',async({page})=>{
 await page.goto('/#page=papers');await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 await page.getByRole('button',{name:'原始 PDF',exact:true}).click();
 await expect(page.getByRole('img',{name:'原始论文 PDF · 第 1 页',exact:true})).toBeVisible();
 await page.getByLabel('PDF 页码',{exact:true}).fill('2');
 await expect(page.getByRole('img',{name:'原始论文 PDF · 第 2 页',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'PDF 下一页',exact:true})).toHaveCount(0);
 const first=await page.locator('.pdf-canvas-surface canvas').first().evaluate(el=>el.getBoundingClientRect().width);
 await page.getByRole('button',{name:'PDF 放大',exact:true}).click();
 await expect.poll(()=>page.locator('.pdf-canvas-surface canvas').first().evaluate(el=>el.getBoundingClientRect().width)).toBeGreaterThan(first);
 await page.getByRole('button',{name:'相关文献',exact:true}).click();await expect(page.locator('.related-card').first()).toBeVisible();
});

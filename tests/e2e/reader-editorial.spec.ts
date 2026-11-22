import {test,expect} from '@playwright/test';
import {lessonProse} from '../../web/lessonProse';
test('legacy tutorial lists preserve mathematical indices and equation references',()=>{
 expect(lessonProse('前置知识：(1) 密度 $x_{(1)}$；(2) 梯度。')).toBe('前置知识：\n\n1. 密度 $x_{(1)}$；\n\n2. 梯度。');
 expect(lessonProse('使用式 (1) 与式 (2)。')).toBe('使用式 (1) 与式 (2)。');
 expect(lessonProse('1) 第一项\n2）第二项')).toBe('1. 第一项\n2. 第二项');
 expect(lessonProse('`(1) (2)` $\\phi^\\chi_{\\eta k_0}$')).toBe('`(1) (2)` $\\phi^\\chi_{\\eta k_0}$');
});
test('reader headings share a scale, lists render, math scripts retain KaTeX proportions',async({page})=>{
 // The editing suite persists a new analysis on the shared isolated server.
 // Keep this typography fixture independent of that suite's saved full-text body.
 await page.route('**/api/paper?*',async route=>{
  const response=await route.fetch();const paper=await response.json();
  delete paper.analysis.result.fulltext_markdown;
  await route.fulfill({response,json:paper});
 });
 await page.route('**/api/lessons?*',r=>r.fulfill({json:[{claim_index:0,result:{title:'排版检查',motivation:'密度 $\\phi^\\chi_{\\eta k_0}$',prerequisites:'前置知识：(1) 密度定义；(2) 梯度计算。',symbols:[{symbol:'\\phi^\\chi_{\\eta k_0}',meaning:'密度',domain_units:'无量纲'}],equations:[],derivation:'推导',example:'算例',conclusions:'结论',limitations:'条件',sources:[]}}]}));
 await page.goto('/#page=papers');await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 await expect(page.locator('.reading-section-heading h3')).toHaveCount(3);
 const headings=await page.locator('.reading-section-heading h3').evaluateAll(es=>es.map(e=>getComputedStyle(e).fontSize));
 expect(headings).toEqual(['20px','20px','20px']);
 await page.locator('.lesson-expansion > summary').click();
 await expect(page.locator('.lesson-body ol li')).toHaveCount(2);
 await expect(page.locator('.lesson-caveat')).toHaveCount(0);
 await expect(page.locator('.lesson-body .katex-error')).toHaveCount(0);
 await expect(page.locator('.lesson-body .katex')).toHaveCount(2);
 const ratio=await page.locator('.lesson-body .katex').first().evaluate(el=>{
  const script=el.querySelector('.sizing');return script?parseFloat(getComputedStyle(script).fontSize)/parseFloat(getComputedStyle(el).fontSize):1;
 });expect(ratio).toBeGreaterThan(.45);expect(ratio).toBeLessThan(.85);
});

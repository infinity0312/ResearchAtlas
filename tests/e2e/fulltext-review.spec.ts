import {test,expect} from '@playwright/test';

test('full-text study renders evidence tables and LaTeX inside the reader',async({page})=>{
 await page.route('**/api/paper?*',async route=>{
  const response=await route.fetch();const paper=await response.json();
  paper.analysis.result.fulltext_markdown=String.raw`# GPT-6-Sol 全文重析 · 论文标题

本地 PDF 物理页 1–17 已逐页阅读。解析文本 SHA-256 abc123。

## 方法与证据

令 $Q^\top Q=I$，目标为

$$\min_W \|WX-\widehat W X\|_F^2.$$

| 设置 | 原文结果 | 页码 |
|---|---|---|
| W4A16 | 8.37 | 7 |

结论以原文实验条件为准。`;
  await route.fulfill({response,json:paper});
 });
 await page.goto('/#page=papers');
 await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 const study=page.locator('.fulltext-review');
 await expect(study.getByRole('heading',{name:'全文研读',exact:true})).toBeVisible();
 await expect(study.getByRole('heading',{name:'方法与证据',exact:true})).toBeVisible();
 await expect(study.getByRole('heading',{name:'论文标题',exact:true})).toHaveCount(0);
 await expect(study).not.toContainText('GPT-6-Sol 全文重析');
 await expect(study).not.toContainText('SHA-256');
 await expect(study).not.toContainText('已逐页阅读');
 await expect(study.locator('.katex')).toHaveCount(2);
 await expect(study.locator('.katex-error')).toHaveCount(0);
 await expect(study.getByRole('cell',{name:'8.37',exact:true})).toBeVisible();
 await page.setViewportSize({width:740,height:900});
 await expect(study).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBeTruthy();
});

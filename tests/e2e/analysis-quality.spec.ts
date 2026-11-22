import {test,expect} from '@playwright/test';
import type {AnalysisQuality} from '../../web/api';

const base:AnalysisQuality={contract_version:1,provenance:'evidence_pipeline',evidence:'verified',grounding:'bound',semantic:'not_reviewed',freshness:'current',rejected_evidence:0};
const cases:{name:string;quality:AnalysisQuality;expected:string;binding:string}[]=[
 {name:'legacy',quality:{...base,provenance:'legacy',evidence:'unverified',grounding:'legacy'},expected:'引文未核验',binding:'历史结果尚未经过结论绑定校验'},
 {name:'partial',quality:{...base,evidence:'partial',rejected_evidence:2},expected:'引文部分核验',binding:'结论引用了已通过校验的依据'},
 {name:'stale',quality:{...base,freshness:'stale'},expected:'引文已核验',binding:'结论引用了已通过校验的依据'},
];

for(const fixture of cases){
 test(`reader distinguishes ${fixture.name} evidence from semantic review`,async({page})=>{
  await page.route('**/api/paper?*',async route=>{
   const response=await route.fetch();const paper=await response.json();
   paper.analysis.quality=fixture.quality;
   // Conflicting embedded data must never replace the server's canonical status.
   paper.analysis.result.quality={...base,semantic:'human_reviewed'};
   await route.fulfill({response,json:paper});
  });
  await page.goto('/#page=papers');
  await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
  const quality=page.locator('.analysis-quality');
  await expect(quality).toContainText(fixture.expected);
  await expect(quality.locator('summary')).toContainText('语义未复核');
  await expect(quality).not.toContainText('语义经人工复核');
  if(fixture.name==='stale')await expect(quality.locator('summary')).toContainText('结果待更新');
  await quality.getByLabel('分析质量与核验范围').click();
  await expect(quality.locator('dl')).toBeVisible();
  await expect(quality.locator('dl')).toContainText(fixture.binding);
  await expect(quality).toContainText(`被拒绝的依据 ${fixture.quality.rejected_evidence} 条`);
  await page.setViewportSize({width:390,height:844});
  await expect(quality).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBeTruthy();
 });
}

test('older API responses show no invented quality status',async({page})=>{
 await page.route('**/api/paper?*',async route=>{
  const response=await route.fetch();const paper=await response.json();
  delete paper.analysis.quality;
  paper.analysis.result.quality=base;
  await route.fulfill({response,json:paper});
 });
 await page.goto('/#page=papers');
 await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 await expect(page.locator('.analysis-summary')).toBeVisible();
 await expect(page.locator('.analysis-quality')).toHaveCount(0);
});

test('paper library exposes supplied quality without changing reading navigation',async({page})=>{
 await page.route('**/api/papers?*',async route=>{
  const response=await route.fetch();const list=await response.json();
  for(const paper of list.items)if(paper.analysis)paper.analysis.quality={...base,evidence:'partial',freshness:'stale'};
  await route.fulfill({response,json:list});
 });
 await page.goto('/#page=papers');
 const paper=page.locator('.paper-row').filter({hasText:'Equivariant models for molecular prediction'});
 await expect(paper.locator('.analysis-quality-compact')).toHaveText('引文部分核验 · 待更新 · 语义未复核');
 await paper.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 await expect(page.locator('.analysis-summary')).toBeVisible();
});

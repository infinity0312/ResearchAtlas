import {test,expect} from '@playwright/test';

test('paper feed appends on scroll, resets search, and retries failed continuation',async({page})=>{
 let failed=false;
 await page.route('**/api/papers?*',async route=>{
  const q=new URL(route.request().url()).searchParams;
  const start=Number(q.get('cursor')||0),search=q.get('q')||'';
  if(start===20&&!failed){failed=true;await route.fulfill({status:503,json:{detail:'temporary'}});return}
  const total=search?1:45;
  await route.fulfill({json:{total,next_cursor:start+20<total?String(start+20):null,items:Array.from({length:Math.min(20,total-start)},(_,i)=>({id:String(start+i),title:search?'Filtered result':`Feed paper ${start+i}`,abstract:'An indexed paper abstract.',authors:['Ada'],categories:['cs.LG'],published:new Date().toISOString(),version:1,saved:false,analysis:null}))}});
 });
 await page.goto('/#page=papers&days=30');
 await expect(page.locator('.paper-row')).toHaveCount(20);
 await page.locator('.feed-end').scrollIntoViewIfNeeded();
 await expect(page.locator('.paper-row')).toHaveCount(40);
 await page.locator('.feed-end').scrollIntoViewIfNeeded();
 await expect(page.locator('.paper-row')).toHaveCount(45);
 await expect(page.locator('.feed-end')).toContainText('已显示全部 45 篇');
 await expect(page.getByRole('button',{name:'下一页',exact:true})).toHaveCount(0);
 await page.getByLabel('搜索标题或摘要').fill('Ada');
 await expect(page.locator('.paper-row')).toHaveCount(1);
 await expect(page.locator('.paper-title')).toHaveText('Filtered result');
 await page.getByRole('button',{name:'全部时间',exact:true}).click();
 await expect(page).toHaveURL(/days=0/);
 await page.reload();await expect(page.getByRole('button',{name:'全部时间',exact:true})).toHaveClass('selected');
});

test('map multi-domain filter persists and shared controls have consistent styling',async({page})=>{
 await page.goto('/#page=map&days=30');
 await page.getByRole('button',{name:'选择研究领域（多选）'}).click();
 await page.getByRole('group',{name:'研究领域多选'}).getByLabel('分子与材料').check();
 await page.getByRole('group',{name:'研究领域多选'}).getByLabel('生命科学').check();
 await page.keyboard.press('Escape');
 await expect(page.locator('.tree-domain')).toHaveCount(2);
 await expect(page.locator('.domain-card')).toHaveCount(2);
 await expect(page).toHaveURL(/domain_ids=molecules&domain_ids=life/);
 await page.reload();await expect(page.locator('.tree-domain')).toHaveCount(2);
 await page.getByRole('button',{name:'全部时间',exact:true}).click();
 await expect(page).toHaveURL(/days=0/);
 await expect(page.locator('.notice.error')).toHaveCount(0);
 await expect(page.getByLabel('方法统计粒度')).toHaveCSS('appearance','base-select');
 await page.getByLabel('方法统计粒度').scrollIntoViewIfNeeded();
 await page.screenshot({path:'docs/map-controls-verified.png'});
 await page.goto('/#page=trends');
 await expect(page.locator('.trend-reading')).toHaveCSS('padding','24px');
 await page.locator('.trend-reading').scrollIntoViewIfNeeded();
 await page.screenshot({path:'docs/trend-alignment-verified.png'});
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

import {test,expect} from '@playwright/test';
test('continuous PDF saves normalized highlights, notes and deletes them',async({page})=>{
 await page.goto('/#page=papers');await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();await page.getByRole('button',{name:'原始 PDF',exact:true}).click();
 const span=page.locator('.textLayer span').filter({hasText:'Selectable original paper text.'});await expect(span).toBeVisible();
 await span.evaluate(el=>{const r=document.createRange();r.selectNodeContents(el);window.getSelection()?.removeAllRanges();window.getSelection()?.addRange(r);document.dispatchEvent(new PointerEvent('pointerup',{bubbles:true}))});
 await page.getByRole('button',{name:'高亮标注',exact:true}).click();const highlight=page.getByRole('button',{name:'高亮：Selectable original paper text.',exact:true});await expect(highlight).toBeVisible();
 await page.getByRole('button',{name:'标注 1',exact:true}).click();await page.getByPlaceholder('添加笔记…').fill('Important evidence');await page.getByRole('button',{name:'标注 1',exact:true}).click();
 await page.getByRole('button',{name:'相关文献',exact:true}).click();await page.getByRole('button',{name:'原始 PDF',exact:true}).click();await expect(highlight).toBeVisible();
 if(!await page.getByPlaceholder('添加笔记…').isVisible())await page.getByRole('button',{name:'标注 1',exact:true}).click();await expect(page.getByPlaceholder('添加笔记…')).toHaveValue('Important evidence');
 await page.getByRole('button',{name:/删除标注/}).click();await expect(highlight).toHaveCount(0);
 await page.locator('.pdf-page-host').evaluate(el=>el.scrollTop=el.scrollHeight);await expect(page.getByLabel('PDF 页码',{exact:true})).toHaveValue('2');
});
test('opportunity scatter distinguishes missing data from zero',async({page})=>{
 await page.route('**/api/model-control',r=>r.fulfill({json:{enabled:true}}));
 await page.route('**/api/trends/data?*',r=>r.fulfill({json:{series:[{id:'preset-0',name:'分子性质预测',query:'ti:molecular',color:'#327c72',growth:null,points:[{period:'2025',count:null,partial:false}],insight:{x:null,y:null,growth:null,acceleration:null,status:'数据不足',rebound:false,periods:[]}}]}}));
 await page.goto('/#page=trends');await expect(page.locator('.opportunity-chart')).toHaveAttribute('data-series-count','0');await expect(page.locator('.opportunity-plot')).toBeHidden();await expect(page.locator('.signal-empty')).toBeVisible();await expect(page.getByLabel(/同时分析创新信号/)).toBeChecked();
 await expect(page.locator('.signal-profiles article')).toContainText('缺少三个连续完整周期的有效计数');await expect(page.locator('.signal-profiles')).not.toContainText('0 / 100');
 await page.screenshot({path:'docs/trend-signals.png',fullPage:true});
});
test('populated opportunity map exposes cross-period evidence and fits mobile',async({page})=>{
 await page.route('**/api/trends/data?*',r=>r.fulfill({json:{series:[{id:'preset-0',name:'分子性质预测',color:'#327c72',query:'ti:molecular',points:[{period:'2023',count:80,partial:false},{period:'2024',count:90,partial:false},{period:'2025',count:110,partial:false}],growth:22.2,insight:{x:67,y:58,growth:22.2,acceleration:9.7,status:'可比较',rebound:true,periods:[{period:'2025',sample:24,population:110,opportunity:58,breakthrough:50,incremental:12.5,rigor:65,diversity:3.2,share_error:20,papers:[{id:'2501.00001',title:'Evidence sample',quote:'An exact original abstract excerpt.',bottleneck:'More accurate physical constraints'}]}]}}]}}));
 await page.goto('/#page=trends');await expect(page.locator('.signal-empty')).toHaveCount(0);await expect(page.getByText('启发式高分样本占比回升，请核对样本与检索口径变化')).toBeVisible();await expect(page.getByText(/评分不代表技术成熟度、突破概率或商业价值/)).toBeVisible();await page.getByText('跨期变化与论文依据',{exact:true}).click();await expect(page.getByText('An exact original abstract excerpt.',{exact:true})).toBeVisible();
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

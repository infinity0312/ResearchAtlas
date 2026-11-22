import {test,expect} from '@playwright/test';
test('graph starts with all tags and collapsed controls, clear and select all work',async({page,request})=>{
 await request.post('/api/tags/import-analysis',{headers:{'X-Atlas-Client':'1'}});await page.goto('/#page=map');
 await expect(page.locator('.atlas-network')).toHaveAttribute('data-ready','true');await expect(page.getByRole('button',{name:'切换标签筛选面板'})).toHaveAttribute('aria-expanded','false');await expect(page.locator('.graph-controls')).not.toBeVisible();await expect(page.locator('.paper-legend')).not.toHaveAttribute('open','');
 await page.getByRole('button',{name:'切换标签筛选面板'}).click();await expect(page.locator('.graph-controls')).toBeVisible();for(const box of await page.locator('.graph-tag-list input').all())await expect(box).toBeChecked();
 await page.getByRole('button',{name:'清空选择',exact:true}).click();await expect(page.locator('[data-node-id]')).toHaveCount(0);await page.getByRole('button',{name:'全选标签',exact:true}).click();await expect(page.locator('[data-node-id]').first()).toBeVisible();
 await page.emulateMedia({reducedMotion:'reduce'});expect(await page.locator('.graph-workspace').evaluate(el=>getComputedStyle(el).transitionDuration)).toBe('0s');
});
test('page navigation starts at the top and respects reduced motion',async({page})=>{
 await page.goto('/#page=trends');await page.locator('.page-footer').scrollIntoViewIfNeeded();expect(await page.evaluate(()=>scrollY)).toBeGreaterThan(0);
 await page.getByRole('button',{name:'发现论文',exact:true}).click();await expect.poll(()=>page.evaluate(()=>scrollY)).toBe(0);
 await page.emulateMedia({reducedMotion:'reduce'});expect(await page.locator('main').evaluate(el=>getComputedStyle(el).animationName)).toBe('none');
});

test('collapsed graph rail leaves no invisible height below the canvas',async({page})=>{
 await page.goto('/#page=map');await expect(page.locator('.atlas-network')).toHaveAttribute('data-ready','true');
 for(let i=0;i<3;i++){
 const boxes=await page.locator('.graph-workspace').evaluate(el=>({workspace:el.getBoundingClientRect().height,stage:el.querySelector('.graph-stage')!.getBoundingClientRect().height}));expect(Math.abs(boxes.workspace-boxes.stage)).toBeLessThan(3);
 await page.getByRole('button',{name:'切换标签筛选面板'}).click();await page.getByRole('button',{name:'切换标签筛选面板'}).click();
 }
});

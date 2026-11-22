import {test,expect} from '@playwright/test';
const preferences={edition:'prism',effects:'off',motion:'system',density:'comfortable'};
for(const width of [390,1440])test(`terminal preload hands off without pavilions at ${width}`,async({page})=>{
 await page.setViewportSize({width,height:900});await page.addInitScript(p=>localStorage.setItem('atlas.appearance.v1',JSON.stringify(p)),preferences);
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/#page=overview');await expect(page.getByRole('dialog',{name:'研究终端启动'})).toBeVisible();await expect(page.getByRole('dialog',{name:'研究终端启动'})).toBeHidden({timeout:10000});
 await expect(page.locator('.pavilion-view')).toHaveCount(0);expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
 await page.goto('/#page=settings');await expect(page.getByRole('dialog',{name:'研究终端启动'})).toHaveCount(0);
 await page.getByText('实验性视觉效果',{exact:true}).click();await page.getByRole('button',{name:'重播系统入场'}).click();await expect(page.getByRole('dialog',{name:'研究终端启动'})).toBeVisible();await page.keyboard.press('Escape');await expect(page.getByRole('dialog',{name:'研究终端启动'})).toBeHidden();await expect(page.getByRole('button',{name:'重播系统入场'})).toBeFocused();expect(errors).toEqual([]);
});
test('entry tolerates unavailable index and remains skippable',async({page})=>{
 await page.addInitScript(p=>localStorage.setItem('atlas.appearance.v1',JSON.stringify(p)),preferences);await page.route('**/api/domains',r=>r.fulfill({status:503,json:{detail:'offline'}}));await page.goto('/#page=settings');await expect(page.getByRole('dialog',{name:'研究终端启动'})).toContainText('稍后重试');await page.getByRole('button',{name:'跳过动画'}).click();await expect(page.getByRole('dialog',{name:'研究终端启动'})).toBeHidden();await expect(page.getByText('界面与视觉体验',{exact:true})).toBeVisible();
});
test('classic has no startup gate and reduced motion has no cinematic wait',async({page})=>{
 await page.goto('/#page=settings');await expect(page.getByRole('dialog',{name:'研究终端启动'})).toHaveCount(0);await page.getByRole('button',{name:'Prism 光场工作台',exact:false}).click();await page.getByLabel('动效偏好',{exact:true}).selectOption('reduced');await page.getByText('实验性视觉效果',{exact:true}).click();await page.getByRole('button',{name:'重播系统入场'}).click();await expect(page.getByRole('dialog',{name:'研究终端启动'})).toBeHidden({timeout:2000});
});

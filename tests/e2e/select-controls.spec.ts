import {test,expect} from '@playwright/test';

test('trend dropdown has one icon and a styled picker after lazy page navigation',async({page})=>{
 await page.goto('/#page=trends');
 const select=page.getByLabel('趋势时间粒度');
 await expect(select).toHaveCSS('appearance','base-select');
 await expect(select).toHaveCSS('background-image','none');
 await select.click();
 await expect(page.getByRole('option',{name:'按月',exact:true})).toBeVisible();
 const picker=await select.evaluate(el=>{const s=getComputedStyle(el,'::picker(select)');return {radius:s.borderRadius,bg:s.backgroundColor}});
 expect(picker).toEqual({radius:'12px',bg:'rgb(255, 255, 255)'});
 const fieldBox=await select.boundingBox(),optionBox=await page.getByRole('option',{name:'按年',exact:true}).boundingBox();
 expect(optionBox!.y).toBeGreaterThan(fieldBox!.y+fieldBox!.height);
 await page.screenshot({path:'docs/dropdown-trends-open.png'});
 await page.keyboard.press('Escape');await expect(select).toHaveValue('year');
 await select.click();await page.keyboard.press('End');await page.keyboard.press('Enter');
 await expect(select).toHaveValue('month');
 await expect(page.getByLabel('趋势开始时间')).toHaveValue(/-01$/);
 await page.getByRole('button',{name:'领域地图',exact:true}).click();
 const method=page.getByLabel('方法统计粒度');
 await expect(method).toHaveCSS('background-image','none');
 await expect(method).toHaveCSS('border-radius','9px');
 await method.click();await expect(page.getByRole('option',{name:'具体方法',exact:true})).toBeVisible();
 await page.keyboard.press('End');await page.keyboard.press('Enter');
 await expect(method).toHaveValue('methods');
 await page.getByRole('button',{name:'领域趋势',exact:true}).click();
 await expect(page.getByLabel('趋势时间粒度')).toHaveCSS('background-image','none');
});

test('dropdown in a modal dismisses before its dialog and preserves focus',async({page})=>{
 await page.goto('/#page=map');await page.getByRole('button',{name:'新建标签',exact:true}).click();
 const dialog=page.getByRole('dialog',{name:'新建标签'}),select=dialog.getByLabel('标签类型',{exact:true});
 await select.click();await expect(dialog.getByRole('option',{name:'解决的问题',exact:true})).toBeVisible();
 await page.keyboard.press('Escape');await expect(dialog).toBeVisible();
 await expect(select).toBeFocused();
 await page.keyboard.press('Escape');await expect(dialog).not.toBeVisible();
});

test('narrow screen dropdown stays legible without page overflow',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto('/#page=trends');
 const select=page.getByLabel('趋势时间粒度');await select.click();
 await expect(page.getByRole('option',{name:'按月',exact:true})).toBeVisible();
 const box=await page.getByRole('option',{name:'按月',exact:true}).boundingBox();
 expect(box!.x).toBeGreaterThanOrEqual(0);expect(box!.x+box!.width).toBeLessThanOrEqual(390);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await page.screenshot({path:'docs/dropdown-mobile-open.png'});
});

import {test,expect} from '@playwright/test';
test('classification tree shares the graph history scope',async({page})=>{
 await page.addInitScript(()=>sessionStorage.setItem('atlas.terminal.entered','1'));
 await page.route('**/api/hierarchy?*',r=>{const days=new URL(r.request().url()).searchParams.get('days');return r.fulfill({json:{domains:[],total:days==='0'?27:0,shown:days==='0'?27:0,classified:days==='0'?26:0,truncated:false}})});
 await page.goto('/#page=map&days=30');
 await expect(page.locator('.hierarchy-panel .tag')).toContainText('26 / 27');
 await expect(page.locator('.hierarchy-panel .tag')).toContainText('全部历史');
 await page.getByLabel('全部历史文献',{exact:true}).uncheck();
 await expect(page.locator('.hierarchy-panel .tag')).toContainText('0 / 0');
 await expect(page.locator('.hierarchy-panel .tag')).toContainText('近 30 天');
 await page.getByRole('button',{name:'全部时间',exact:true}).click();
 await expect(page.locator('.hierarchy-panel .tag')).toContainText('26 / 27');
 await expect(page.getByLabel('全部历史文献',{exact:true})).toBeChecked();
 await page.getByRole('button',{name:'近 7 天',exact:true}).click();
 await expect(page.getByLabel('全部历史文献',{exact:true})).not.toBeChecked();
 await expect(page.locator('.hierarchy-panel .tag')).toContainText('近 7 天');
});

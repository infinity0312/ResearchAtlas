import {test,expect} from '@playwright/test';
test('sidebar domains always open the corresponding paper library',async({page})=>{
 for(const source of ['jobs','map','trends','papers']){
  await page.goto('/#page='+source+'&days=90');await page.locator('.domain-nav button').filter({hasText:'分子与材料'}).click();
  await expect(page.locator('.page-heading h1')).toContainText('发现论文');await expect(page.getByLabel('选择研究领域')).toHaveValue('molecules');await expect(page.getByRole('button',{name:'全部时间',exact:true})).toHaveClass(/selected/);
  await expect(page).toHaveURL(/page=papers.*domain=molecules/);
  await page.locator('.domain-nav button').filter({hasText:'分子与材料'}).click();await expect(page.getByLabel('选择研究领域')).toHaveValue('molecules');
 }
});

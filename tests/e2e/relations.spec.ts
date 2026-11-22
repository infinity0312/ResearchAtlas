import {test,expect} from '@playwright/test';
test('directed evidence is independent of similarity filtering and supports timeline',async({page})=>{
 const papers=[{id:'a',title:'QuaRot: Outlier-Free inference',label:'QuaRot',published:'2024-03-01'},{id:'b',title:'SpinQuant: Learned rotations',label:'SpinQuant',published:'2024-05-01'}];
 await page.route('**/api/graph?*',r=>r.fulfill({json:{papers,tags:[],links:[],total:2,truncated:false,relations:[{id:'rel',source_id:'b',target_id:'a',kind:'cites',evidence:{page:3,quote:'QuaRot: Outlier-Free inference'}}]}}));
 await page.goto('/#page=map');await expect(page.locator('.atlas-network')).toHaveAttribute('data-ready','true');
 await expect(page.locator('.network-edge[data-kind=cites]')).toHaveCount(1);await expect(page.locator('.network-edge')).toHaveAttribute('marker-end','url(#relation-arrow)');
 await expect(page.locator('.network-edge title')).toContainText('第 3 页');
 await page.getByLabel('图谱视图',{exact:true}).selectOption('timeline');await expect(page.getByRole('img',{name:'论文时间轴散点图'})).toBeVisible();await expect(page.locator('.atlas-network')).toHaveCount(0);
 await page.getByLabel('图谱视图',{exact:true}).selectOption('similarity');await expect(page.getByRole('img',{name:'论文分类相似度矩阵'})).toBeVisible();await page.getByLabel('图谱视图',{exact:true}).selectOption('network');await expect(page.locator('.network-edge[data-kind=cites]')).toHaveCount(1);
 await page.screenshot({path:'docs/graph-relations-timeline.png'});
});

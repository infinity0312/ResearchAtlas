import {test,expect} from '@playwright/test';
import {similarityMatrix} from '../../web/paperViewData';
const papers=[{id:'a',title:'First paper',label:'First',published:'2000-01-01'},{id:'b',title:'Second paper',label:'Second',published:'2020-01-01'},{id:'c',title:'Without labels or date',label:'Third'}];
const tags=[{id:'m',name:'Method',kind:'method',description:'',count:2,archived:false}];
const links=[{paper_id:'a',tag_id:'m',source:'manual'},{paper_id:'b',tag_id:'m',source:'manual'}];
test('matrix is symmetric, identical classifications score one, missing labels remain absent',()=>{
 const m=similarityMatrix({papers,tags,links,total:3,truncated:false});expect(m.cells).toEqual([[0,0,1],[0,1,1],[1,0,1],[1,1,1]]);
});
for(const width of [390,1440])test(`three distinct paper views at ${width}`,async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await page.setViewportSize({width,height:950});
 await page.route('**/api/graph?*',r=>r.fulfill({json:{papers,tags,links,total:3,truncated:false,relations:[]}}));
 await page.goto('/#page=map');const view=page.getByLabel('图谱视图',{exact:true});await expect(view).toHaveValue('network');
 for(let round=0;round<2;round++){
 await view.selectOption('similarity');await expect(page.getByRole('img',{name:'论文分类相似度矩阵'})).toBeVisible();await expect(page.locator('.atlas-network')).toHaveCount(0);await page.locator('.pv-index-list button').first().click();await expect(page.locator('.paper-view-pair')).toContainText('First paper');
 await view.selectOption('timeline');await expect(page.getByRole('img',{name:'论文时间轴散点图'})).toBeVisible();await expect(page.getByText('1 篇缺少有效日期，暂未定位')).toBeVisible();
 await page.getByRole('button',{name:'最近十年',exact:true}).click();await page.getByRole('button',{name:'全部历史',exact:true}).click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
 await view.selectOption('network');await expect(page.locator('.atlas-network')).toHaveAttribute('data-ready','true');
 }
 expect(errors).toEqual([]);
});

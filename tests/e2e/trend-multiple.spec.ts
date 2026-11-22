import {test,expect} from '@playwright/test';
const selected=['preset-0','preset-1','preset-4','preset-6','preset-7'];
test('five curves and life science points survive reload; missing analysis can be queued independently',async({page})=>{
 await page.addInitScript(()=>{if(!localStorage.getItem('atlas.trends.selection'))localStorage.setItem('atlas.trends.selection',JSON.stringify({ids:['preset-0','preset-1','preset-4','preset-6','preset-7'],start:'2020',end:'2025',interval:'year'}))});
 await page.route('**/api/trends/data?*',async route=>{const response=await route.fetch();const body=await response.json();body.series=body.series.map((r:any,i:number)=>({...r,points:r.points.map((p:any,k:number)=>({...p,count:20+i*17+k*12})),insight:{x:30+i*10,y:50+i*5,periods:[],status:'可比较'}}));await route.fulfill({json:body})});
 await page.goto('/#page=trends');
 const lines=page.getByRole('img',{name:'arXiv 小方向论文数量时间趋势图'}),scatter=page.getByRole('img',{name:'各领域增长阶段与创新空间散点图'});
 await expect(lines).toHaveAttribute('data-series-count','5',{timeout:20000});await expect(scatter).toHaveAttribute('data-series-count','5');
 await page.getByRole('button',{name:'展开或收起：生命科学 · 全领域',exact:true}).click();await page.getByLabel('选择趋势方向：蛋白质设计',{exact:true}).check();await expect(lines).toHaveAttribute('data-series-count','6');
 await page.reload();await expect(lines).toHaveAttribute('data-series-count','6');await expect(scatter).toHaveAttribute('data-series-count','6');
 await page.screenshot({path:'docs/trend-six-series.png',fullPage:true});
});
test('unrelated running statistics do not block life science analysis',async({page})=>{
 await page.addInitScript(()=>localStorage.setItem('atlas.trends.selection',JSON.stringify({ids:['preset-6'],start:'2020',end:'2025',interval:'year'})));
 await page.route('**/api/jobs',route=>route.fulfill({json:[{id:'other',kind:'trends',status:'running',message:'OTHER',payload:{ids:['preset-0'],start:'2020',end:'2025',interval:'year'},progress:0}]}));
 let requested:any;
 await page.route('**/api/trends/refresh',async route=>{requested=route.request().postDataJSON();await route.fulfill({status:202,json:{job_id:'new'}})});
 await page.goto('/#page=trends');const button=page.getByRole('button',{name:'补齐统计与创新分析',exact:true});await expect(button).toBeEnabled({timeout:20000});await button.click();await expect.poll(()=>requested).toEqual({ids:['preset-6'],start:'2020',end:'2025',interval:'year',quality:true});
});

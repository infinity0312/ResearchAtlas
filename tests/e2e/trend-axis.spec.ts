import {test,expect} from '@playwright/test';
import {timeTicks} from '../../web/spatial/timeTicks';

test('UTC calendar ticks refine with zoom and support single-date data',()=>{
 const lo=Date.parse('2000-01-01'),hi=Date.parse('2025-12-31');
 const wide=timeTicks(lo,hi,800),close=timeTicks(lo,hi,800*12);
 expect(close.length).toBeGreaterThan(wide.length);
 expect(wide.every(t=>t.text.length===4)).toBe(true);
 expect(close.some(t=>t.text.length===7)).toBe(true);
 expect(timeTicks(lo,lo,800)).toEqual([{x:0,text:'2000-01-01'}]);
 expect(timeTicks(Date.parse('2025-01-01'),Date.parse('2025-01-20'),800).some(t=>t.text.length===10)).toBe(true);
});

test('more than six directions stay selectable and requests remain bounded',async({page})=>{
 await page.addInitScript(()=>{sessionStorage.setItem('atlas.terminal.entered','1');localStorage.setItem('atlas.trends.selection',JSON.stringify({ids:['s0','s1','s2','s3','s4','s5'],start:'2020',end:'2025',interval:'year'}))});
 const names=['A','B','C','D','E','F','机器学习原子势','材料逆向设计'];
 const rows=names.map((name,i)=>({id:'s'+i,name,query:'ti:"'+name+'"',domain_id:'molecules',color:'#537f70',is_root:false}));
 await page.route('**/api/trends/series',r=>r.fulfill({json:[{id:'root',name:'分子与材料 · 全领域',query:'cat:cond-mat.mtrl-sci',color:'#537f70',domain_id:'molecules',is_root:true},...rows]}));
 const batches:number[]=[];
 await page.route('**/api/trends/data?*',r=>{const ids=new URL(r.request().url()).searchParams.getAll('ids');batches.push(ids.length);return r.fulfill({json:{series:rows.filter(row=>ids.includes(row.id)).map(row=>({...row,points:[{period:'2020',count:1,partial:false}],growth:null}))}})});
 await page.goto('/#page=trends');await page.getByRole('button',{name:'展开或收起：分子与材料 · 全领域',exact:true}).click();
 for(const name of names.slice(6)){const box=page.getByLabel('选择趋势方向：'+name,{exact:true});await expect(box).toBeEnabled();await box.check();await expect(box).toBeChecked()}
 await expect(page.locator('.macro-chart')).toHaveAttribute('data-series-count','8');expect(Math.max(...batches)).toBeLessThanOrEqual(6);
});

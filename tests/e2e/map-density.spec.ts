import {test,expect} from '@playwright/test';

test('multi-domain trees retain complete branches without clipping long labels or mounting closed leaves',async({page})=>{
 const papers=Array.from({length:500},(_,i)=>({id:'tree-'+i,title:'VeryLongUnbrokenScientificTitle'.repeat(5)+' '+i,methods:['LongMethod'.repeat(12)]}));
 const domains=Array.from({length:3},(_,i)=>({id:'density-domain-'+i,name:'跨学科长领域名称'.repeat(8)+i,version:1,origin:'隔离测试分类',topics:[{name:'多尺度方法与适用条件'.repeat(10),papers}],pending:[]}));
 await page.route('**/api/hierarchy?*',route=>route.fulfill({json:{domains,total:500,shown:500,classified:500,truncated:false}}));
 await page.goto('/#page=map');
 await expect(page.locator('.tree-domain')).toHaveCount(3);
 await expect(page.locator('.tree-paper')).toHaveCount(0);
 await page.locator('.tree-domain').first().click();
 await expect(page.locator('.tree-topic-name')).toHaveCount(1);
 await page.locator('.tree-topic').first().click();
 await expect(page.locator('.tree-paper')).toHaveCount(500);
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:900});
  expect(await page.locator('.taxonomy-tree').evaluate(el=>el.scrollWidth<=el.clientWidth+1)).toBeTruthy();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  const leaf=page.locator('.tree-paper').last();await leaf.scrollIntoViewIfNeeded();await expect(leaf).toBeInViewport();
 }
 await page.getByRole('button',{name:'收起所有领域',exact:true}).click();
 await expect(page.locator('.tree-paper')).toHaveCount(0);
 await expect(page.locator('.tree-domain')).toHaveCount(3);
});

for(const edition of ['classic','prism'])test(`${edition} dense similarity retains all papers and locates unclassified papers honestly`,async({page})=>{
 await page.addInitScript(edition=>{localStorage.setItem('atlas.appearance.v1',JSON.stringify({edition,effects:edition==='prism'?'auto':'off',motion:'reduced'}));sessionStorage.setItem('atlas.terminal.entered','1')},edition);
 const papers=Array.from({length:120},(_,i)=>({id:'matrix-'+i,title:'Density research paper '+i,label:'D'+i,published:'2025-01-01'}));
 const tags=[{id:'shared',name:'Shared classification',kind:'topic',count:119,archived:false,description:'Fixture'}];
 await page.route('**/api/graph?*',route=>route.fulfill({json:{papers,tags,links:papers.slice(0,119).map(p=>({paper_id:p.id,tag_id:'shared',source:'manual'})),relations:[],total:120,truncated:false}}));
 await page.goto('/#page=map');await page.getByLabel('图谱视图',{exact:true}).selectOption('similarity');
 await expect(page.locator('.paper-view')).toHaveAttribute('data-total-papers','120');
 await expect(page.locator('.pv-index-list button')).toHaveCount(120);
 await page.getByLabel('查找并定位相似矩阵文献',{exact:true}).fill('Density research paper 119');
 await expect(page.locator('.pv-index-list button')).toHaveCount(1);
 await page.locator('.pv-index-list button').click();
 await expect(page.locator('.paper-view-detail')).toContainText('缺少分类标签，无法计算相似度');
 await expect(page.locator('.paper-view')).toHaveAttribute('data-total-papers','120');
 await page.getByLabel('查找并定位相似矩阵文献',{exact:true}).fill('');
 await expect(page.locator('.pv-index-list button')).toHaveCount(120);
});

test('a comparison range from an old history scope is explicit and recoverable',async({page})=>{
 await page.addInitScript(()=>{localStorage.setItem('atlas.appearance.v1',JSON.stringify({edition:'classic',effects:'off',motion:'reduced'}));sessionStorage.setItem('atlas.terminal.entered','1')});
 await page.route('**/api/graph?*',route=>{
  const all=new URL(route.request().url()).searchParams.get('days')==='0';
  const papers=Array.from({length:3},(_,i)=>({id:(all?'old-':'new-')+i,title:(all?'Old':'New')+' paper '+i,label:'P'+i}));
  return route.fulfill({json:{papers,tags:[],links:[],relations:[],total:3,truncated:false}});
 });
 await page.goto('/#page=map&days=30');await page.getByLabel('图谱视图',{exact:true}).selectOption('similarity');
 const range=page.locator('.matrix-range');await range.locator('summary').click();
 await range.getByRole('button',{name:'清空',exact:true}).click();
 await range.getByLabel('比较论文：P0',{exact:true}).check();
 await range.getByRole('button',{name:'应用范围',exact:true}).click();
 await expect(page.locator('.paper-view')).toHaveAttribute('data-total-papers','1');
 await page.getByLabel('全部历史文献',{exact:true}).uncheck();
 await expect(page.getByRole('status').filter({hasText:'不在当前领域或时间筛选内'})).toBeVisible();
 await expect(range.locator('summary')).toContainText('0 篇当前论文');
 await page.getByRole('button',{name:'恢复当前筛选的全部论文',exact:true}).click();
 await expect(page.locator('.paper-view')).toHaveAttribute('data-total-papers','3');
 await expect(page.locator('.pv-index-list button')).toHaveCount(3);
});

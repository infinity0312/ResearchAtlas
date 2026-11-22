import {expect,test} from '@playwright/test';
import {timelineDate} from '../../web/paperViewData';

test('timeline respects precision and date source',()=>{
 const paper={id:'a',title:'A',published:'2021-01-01'};
 expect(timelineDate({...paper,date_basis:'published-year'})).toMatchObject({kind:'year',date:'2021'});
 expect(timelineDate({...paper,date_basis:'announcement'}).kind).toBe('announcement');
 expect(timelineDate({...paper,date_basis:'imported'}).kind).toBe('imported');
 expect(timelineDate({...paper,date_basis:'published'}).kind).toBe('exact');
 expect(timelineDate({...paper,published:'2021-02-30'}).kind).toBe('unknown');
});

test('each view exposes a distinct research task at narrow width',async({page})=>{
 await page.setViewportSize({width:390,height:850});
 await page.addInitScript(()=>sessionStorage.setItem('atlas.terminal.entered','1'));
 const papers=[
  {id:'a',title:'Alpha method',label:'Alpha',published:'2018-02-02',date_basis:'submitted'},
  {id:'b',title:'Beta benchmark',label:'Beta',published:'2021-04-05',date_basis:'published'},
  {id:'c',title:'Early paper',label:'Early',published:'2018-01-01',date_basis:'published-year'},
  {id:'d',title:'Daily notice',label:'Notice',published:'2022-04-01',date_basis:'announcement'},
 ];
 const tags=[{id:'m',kind:'method',name:'迭代优化'},{id:'n',kind:'method',name:'稀疏搜索'}];
 const links=[{paper_id:'a',tag_id:'m'},{paper_id:'b',tag_id:'m'},{paper_id:'b',tag_id:'n'}];
 const relations=[{id:'1',source_id:'b',target_id:'a',kind:'cites',evidence:{version:2,page:4,quote:'Bibliography entry for Alpha method.'}}];
 await page.route('**/api/graph?*',route=>route.fulfill({json:{papers,tags,links,relations,total:4,truncated:false}}));
 await page.goto('/#page=map&days=0');
 await page.getByLabel('追溯论文',{exact:true}).selectOption('a');
 await page.locator('.graph-research-result').getByText('引用 · Beta benchmark · 来源第 4 页',{exact:true}).click();
 await expect(page.getByRole('link',{name:'核对引用者原页 ↗'})).toHaveAttribute('href','/api/paper/pdf?id=b&version=2#page=4');
 await page.getByRole('button',{name:'此篇指向 · 0'}).click();
 await expect(page.getByText('当前范围内暂无这个方向的关系记录。')).toBeVisible();
 const view=page.getByLabel('图谱视图',{exact:true});
 await view.selectOption('similarity');
 await page.locator('.pv-index-list button').first().click();
 await page.locator('.graph-research-similar button').filter({hasText:'Beta benchmark'}).click();
 await expect(page.locator('.paper-view-detail')).toContainText('共享方法：迭代优化');
 await expect(page.locator('.paper-view-detail')).toContainText('Beta独有：稀疏搜索');
 await view.selectOption('timeline');
 await page.getByLabel('定位年份',{exact:true}).selectOption('2018');
 await expect(page.locator('.paper-view[data-view="timeline"]')).toHaveAttribute('data-total-papers','1');
 await page.getByText('按时间查看论文 · 2 篇',{exact:true}).click();
 await expect(page.getByRole('button',{name:/Early paper.*仅知年份/})).toBeVisible();
 await page.getByText('1 篇缺少有效日期，暂未定位',{exact:true}).click();
 await expect(page.getByRole('button',{name:/Daily notice.*公告记录/})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

import {expect,test,type Page} from '@playwright/test';
import {appearanceKey} from '../../web/ui/Appearance';

async function useIndustrial(page:Page){
 await page.addInitScript(key=>localStorage.setItem(key,JSON.stringify({edition:'industrial'})),appearanceKey);
}

test('old browser preferences open in the only available edition',async({page})=>{
 await page.addInitScript(()=>localStorage.setItem('atlas.appearance.v1',JSON.stringify({edition:'prism',motion:'reduced'})));
 await page.goto('/#page=settings');
 await expect(page.locator('html')).toHaveAttribute('data-edition','industrial');
 await expect(page.locator('html')).toHaveAttribute('data-motion','reduced');
 await expect(page.getByRole('group',{name:'界面版本'})).toHaveCount(0);
 await page.goto('/#page=papers');
 await expect(page.locator('.paper-row').first()).toBeVisible();
 const thumb=await page.locator('.paper-row').first().evaluate(el=>getComputedStyle(el).scrollbarColor);
 expect(thumb).toBe('rgb(170, 168, 160) rgba(0, 0, 0, 0)');
});
test('opening a project brief moves the fold to its actual row and keeps the directory in place',async({page})=>{
 await useIndustrial(page);
 const project={
  id:'atlas-ui-demo',title:'功能材料路线评审',scenario:'route_review',
  owner:'材料研发组',question:'哪个候选材料能在相同工况下通过性能与耐久性验证？',
  recommendation:'在统一工况下开展小样对照试验，保留论文中的温度与载荷边界。',
  criteria:[{id:'performance',label:'性能'},{id:'durability',label:'耐久性'}],
  revision:3,status:'draft',open_questions:'长周期工况下的数据仍需验证。',
  created:'2026-10-01',updated:'2026-10-12',
 };
 const readiness={can_review:false,can_deliver:false,evidence_count:2,blockers:['补齐耐久性证据']};
 await page.route('**/api/projects**',route=>{
  const path=new URL(route.request().url()).pathname;
  if(path==='/api/projects')return route.fulfill({json:{items:[{...project,evidence_count:2,delivery_count:0,readiness}],total:1}});
  if(path.endsWith('/impacts'))return route.fulfill({json:{items:[],total:0}});
  if(path.endsWith(project.id))return route.fulfill({json:{project,readiness,evidence:[],reviews:[],deliveries:[],validations:[],events:[]}});
  return route.continue();
 });
 await page.goto('/#page=projects');
 await expect(page.getByRole('button',{name:'新建研发项目'})).toHaveCSS('background-color','rgb(242, 237, 100)');
 const row=page.getByRole('button',{name:/功能材料路线评审/});
 await row.click();
 await expect(row).toHaveAttribute('aria-expanded','true');
 await expect(row).toHaveCSS('box-shadow',/rgb\(242, 237, 100\)/);
 const brief=page.getByRole('region',{name:'功能材料路线评审简报'});
 await expect(brief).toContainText('当前修订 3');
 await expect(brief).toContainText('补齐耐久性证据');
 if(process.env.ATLAS_UI_PREVIEWS)await page.screenshot({path:process.env.ATLAS_UI_PREVIEWS+'/atlas-industrial-projects.png',animations:'disabled'});
 await brief.getByRole('button',{name:'收起简报',exact:true}).click();
 await expect(row).toBeFocused();
 await expect(row).toHaveAttribute('aria-expanded','false');
 await expect(page).toHaveURL(/#page=projects/);
});

test('industrial reader marks the selected chapter and source, opens the cited PDF and returns to context',async({page})=>{
 await useIndustrial(page);
 await page.route('**/api/paper?*',async route=>{
  const response=await route.fetch();
  const data=await response.json();
  if(data.id==='2609.00000')data.analysis.result.claims.push({kind:'contribution',basis:'author',text:'工业图册依据核查',page:2,quote:'Fixture quotation for evidence navigation.'});
  await route.fulfill({response,json:data});
 });
 await page.goto('/#page=papers');
 await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 const reader=page.getByRole('dialog',{name:'论文阅读'});
 const navigation=reader.getByRole('navigation',{name:'阅读章节'});
 const trigger=reader.getByRole('button',{name:/工业图册依据核查/});
 await trigger.click();
 const source=reader.locator('.atlas-source-sign:visible');
 await expect(source).toContainText('第 2 页');
 await expect(reader.locator('.atlas-selected-claim')).toContainText('工业图册依据核查');
 await expect(navigation.locator('[aria-current=location]')).toHaveCSS('background-color','rgb(242, 237, 100)');
 await expect(source.locator('.atlas-source-marker')).toHaveCSS('background-color','rgb(242, 237, 100)');
 if(process.env.ATLAS_UI_PREVIEWS)await page.screenshot({path:process.env.ATLAS_UI_PREVIEWS+'/atlas-industrial-reader.png',animations:'disabled'});
 await source.getByRole('button',{name:'在 PDF 中查看此页'}).click();
 await expect(reader.getByLabel('PDF 页码',{exact:true})).toHaveValue('2');
 await expect(reader.getByRole('img',{name:'原始论文 PDF · 第 2 页',exact:true})).toBeVisible();
 await reader.locator('.pdf-reading .atlas-return-context').click();
 await expect(trigger).toBeFocused();
});

test('industrial pages and the three map views fit on a phone at 390 pixels',async({page})=>{
 await useIndustrial(page);
 await page.setViewportSize({width:390,height:844});
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.route('**/api/graph?*',route=>route.fulfill({json:{
  papers:[{id:'p1',title:'First paper',published:'2018-02-02',date_basis:'published'},{id:'p2',title:'Second paper',published:'2022-02-02',date_basis:'published'}],
  tags:[{id:'method',kind:'method',name:'Example method'}],
  links:[{paper_id:'p1',tag_id:'method'},{paper_id:'p2',tag_id:'method'}],
  relations:[],total:2,truncated:false,
 }}));
 for(const route of ['projects','papers','trends','settings','map']){
  await page.goto('/#page='+route+'&days=0');
  await expect(page.locator('.app-shell')).toHaveAttribute('data-page',route);
  await expect(page.locator('.page-heading h1')).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('data-motion','reduced');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
 }
 await expect(page.locator('.atlas-network')).toHaveAttribute('data-ready','true');
 await expect(page.locator('.spatial-stage')).toHaveCount(0);
 for(const mode of ['similarity','timeline']){
  await page.getByLabel('图谱视图',{exact:true}).selectOption(mode);
  await expect(page.locator('.paper-view-chart')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
 }
});

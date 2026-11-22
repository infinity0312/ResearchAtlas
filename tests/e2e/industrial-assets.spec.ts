import {expect,test} from '@playwright/test';

test.beforeEach(async({page})=>{
 await page.addInitScript(()=>localStorage.setItem('atlas.appearance.v1',JSON.stringify({edition:'industrial'})));
});

test('contours, printed marks and pointer motion follow the page and motion preference',async({page})=>{
 await page.goto('/#page=papers');
 const heading=page.locator('.page-heading');
 const contour=heading.locator('.atlas-contour-motion');
 await expect(contour).toHaveCSS('animation-name','ef-wipe-in');
 const ordinary=await contour.evaluate(el=>getComputedStyle(el,'::before').backgroundImage);
 expect(ordinary).toContain('endfield-contour-');
 await expect(heading.locator('.ef-tri i')).toHaveCount(3);
 await expect(heading.locator('.eyebrow')).toHaveCSS('font-family',/Saira Atlas/);
 await heading.hover({position:{x:18,y:18}});
 await expect.poll(()=>contour.evaluate(el=>(el as HTMLElement).style.getPropertyValue('--mx'))).not.toBe('');
 await page.locator('.search-shortcut').hover();
 expect(await contour.evaluate(el=>(el as HTMLElement).style.getPropertyValue('--mx'))).toBe('');
 const primary=heading.getByRole('button',{name:'论文探索'});
 await primary.hover();
 expect(await primary.evaluate(el=>getComputedStyle(el,'::after').animationName)).toBe('ef-edge');
 await page.goto('/#page=map&days=0');
 await expect.poll(()=>contour.evaluate(el=>getComputedStyle(el,'::before').backgroundImage)).toContain('endfield-contour-secondary-');
 await page.emulateMedia({reducedMotion:'reduce'});
 await expect(contour).toHaveCSS('animation-name','none');
 await heading.hover({position:{x:18,y:18}});
 expect(await contour.evaluate(el=>(el as HTMLElement).style.getPropertyValue('--mx'))).toBe('');
 if(process.env.ATLAS_UI_PREVIEWS){
  await page.locator('.relation-panel').waitFor();
  await page.screenshot({path:process.env.ATLAS_UI_PREVIEWS+'/atlas-contour-map.png',animations:'disabled'});
 }
});

test('loading uses the static Endfield skeleton until the paper response arrives',async({page})=>{
 let resume=()=>{};
 const loading=new Promise<void>(resolve=>{resume=resolve});
 await page.route('**/api/papers?*',async route=>{await loading;await route.continue()});
 try{
  await page.goto('/#page=papers');
  await expect(page.locator('.atlas-loading .ef-skeleton')).toHaveCount(3);
  await expect(page.locator('.atlas-loading .ef-skeleton').first()).toHaveCSS('animation-name','none');
 }finally{resume()}
 await expect(page.locator('.paper-row').first()).toBeVisible();
 await expect(page.locator('.atlas-loading')).toHaveCount(0);
});

test('evidence dial exposes real counts and a keyboard link to the relevant criterion',async({page,request,baseURL})=>{
 expect(new URL(baseURL!).port).toBe('8770');
 const response=await request.post('/api/projects',{headers:{'X-Atlas-Client':'1'},data:{
  title:'覆盖索引验收',scenario:'route_review',owner:'隔离测试',question:'哪些评价标准已有有效证据？',
  constraints:'仅使用隔离测试数据',criteria:[{id:'performance',label:'同工况性能'},{id:'durability',label:'长周期耐久性'}],
 }});
 expect(response.ok()).toBeTruthy();
 const project=await response.json();
 await page.goto('/#page=projects&project_id='+encodeURIComponent(project.id));
 await page.getByRole('button',{name:'核对证据',exact:true}).click();
 const dial=page.getByRole('group',{name:'证据覆盖导航'});
 await expect(dial.locator('.seg')).toHaveCount(4);
 await expect(dial.locator('.core')).toHaveText('2项');
 await expect(dial.locator('.seg').first()).toHaveCSS('animation-name','ef-assemble');
 const gap=dial.getByRole('link',{name:'缺有效证据：2项'});
 await expect(gap).toBeVisible();
 if(process.env.ATLAS_UI_PREVIEWS){
  await gap.hover();
  await page.screenshot({path:process.env.ATLAS_UI_PREVIEWS+'/atlas-evidence-index.png',animations:'disabled'});
 }
 await gap.focus();
 await expect(dial.locator('.on-tag')).toHaveText('缺证据');
 await gap.press('Enter');
 await expect(page.locator('tr[data-criterion-id=performance]')).toBeFocused();
 await expect(page).toHaveURL(new RegExp('project_id='+project.id));
 await page.setViewportSize({width:390,height:844});
 await page.emulateMedia({reducedMotion:'reduce'});
 await expect(dial.locator('.seg').first()).toHaveCSS('animation-name','none');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

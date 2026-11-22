import {test,expect} from '@playwright/test';

for(const edition of ['classic','prism'])for(const width of [1440,1024,390]){
 test(`Atlas project directory remains readable at ${width}px in ${edition}`,async({page})=>{
  await page.setViewportSize({width,height:900});
  await page.addInitScript(({edition})=>{sessionStorage.setItem('atlas.terminal.entered','1');localStorage.setItem('atlas.appearance.v1',JSON.stringify({edition,motion:'reduced',effects:'off',density:'comfortable',quality:'auto'}))},{edition});
  await page.goto('/#page=projects');
  await expect(page.getByRole('heading',{name:'研发项目',level:1})).toBeVisible();
  await expect(page.locator('.atlas-projects')).toBeVisible();
  await expect(page.getByRole('button',{name:'新建研发项目',exact:true}).first()).toBeVisible();
  const layout=await page.evaluate(()=>{
   const root=document.querySelector('.atlas-projects')!;
   const title=document.querySelector('.page-heading h1')!;
   return {overflow:document.documentElement.scrollWidth>innerWidth+1,titleSize:parseFloat(getComputedStyle(title).fontSize),titleWidth:title.getBoundingClientRect().width};
  });
  expect(layout.overflow).toBeFalsy();expect(layout.titleSize).toBeGreaterThanOrEqual(25);expect(layout.titleWidth).toBeGreaterThan(140);
  await page.screenshot({path:`docs/design/atlas-directory-${edition}-${width}.png`,fullPage:true});
 });
}

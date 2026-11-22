import {expect,test} from '@playwright/test';
import {editionSwatch} from '../../web/ui/industrial/colors';
import {paperColor} from '../../web/graphProjection';

test('industrial display translates legacy defaults and keeps individually assigned colors',()=>{
 expect(editionSwatch('#327C72','industrial')).toBe('#496983');
 expect(editionSwatch('#7e964b','industrial')).toBe('#6a718c');
 expect(editionSwatch('#318845','industrial')).toBe('#318845');
 expect(editionSwatch('#327c72','classic')).toBe('#327c72');
 for(const id of ['2609.00000','first','method','archive']){
  const hue=Number(paperColor(id,true).match(/hsl\((\d+)/)?.[1]);
  expect(hue<=48||hue>=200).toBe(true);
 }
});

test('the brand, domain swatch and reader evidence use the graphite edition',async({page,request})=>{
 await page.addInitScript(()=>localStorage.setItem('atlas.appearance.v1',JSON.stringify({edition:'industrial',motion:'reduced'})));
 await page.goto('/#page=papers&days=0');
 const logo=page.locator('.brand img');
 await expect(logo).toHaveAttribute('src','/favicon.svg?v=2');
 await expect(page.locator('link[rel=icon]')).toHaveAttribute('href','/favicon.svg?v=2');
 const asset=await request.get(await logo.getAttribute('src')||'/favicon.svg');
 expect(await asset.text()).toContain('#f2ed64');
 expect(await asset.text()).not.toContain('#164e46');
 await expect(page.locator('.domain-nav button').filter({hasText:'分子与材料'}).locator('i')).toHaveCSS('background-color','rgb(73, 105, 131)');
 await expect(page.locator('.paper-mark').first()).toHaveCSS('color','rgb(66, 66, 66)');
 const selector=page.getByLabel('选择研究领域',{exact:true});
 const arrow=await selector.evaluate(el=>CSS.supports('appearance','base-select')
  ?getComputedStyle(el,'::picker-icon').borderRightColor
  :getComputedStyle(el).backgroundImage);
 expect(arrow).toMatch(/rgb\(89, 89, 88\)|%23595958/);
 if(process.env.ATLAS_UI_PREVIEWS)await page.screenshot({path:process.env.ATLAS_UI_PREVIEWS+'/graphite-library.png'});
 await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();
 const reader=page.getByRole('dialog',{name:'论文阅读'});
 await expect(reader.locator('.tag.green').first()).toHaveCSS('color','rgb(73, 105, 131)');
 if(process.env.ATLAS_UI_PREVIEWS)await page.screenshot({path:process.env.ATLAS_UI_PREVIEWS+'/graphite-reader.png'});
});

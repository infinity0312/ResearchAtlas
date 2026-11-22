import {test,expect} from '@playwright/test';
test.setTimeout(120000);
const preference={edition:'prism',effects:'auto',motion:'reduced',quality:'balanced'};
for(const width of [390,1440])test(`pavilion modules load original assets and remain bounded at ${width}`,async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await page.setViewportSize({width,height:1000});await page.addInitScript(p=>localStorage.setItem('atlas.appearance.v1',JSON.stringify(p)),preference);
 for(const module of ['overview','papers','trends','surveys','saved','notes','jobs','settings']){
  await page.goto('/#page='+module);const stage=page.locator('.pavilion-view');await stage.scrollIntoViewIfNeeded();await expect(stage).toHaveAttribute('data-ready','true',{timeout:15000});await expect(stage).toHaveAttribute('data-asset',module+'.glb');expect(Number(await stage.getAttribute('data-triangles'))).toBeGreaterThan(1000);expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  await page.getByRole('button',{name:'收起模块空间',exact:true}).click();await expect(stage).toHaveCount(0);await page.getByRole('button',{name:'展开模块空间',exact:true}).click();await expect(stage).toHaveAttribute('data-ready','true',{timeout:15000});
 }
 expect(errors).toEqual([]);
});
test('spatial directory opens the selected real paper and note; editing gives the space back',async({page})=>{
 await page.addInitScript(p=>localStorage.setItem('atlas.appearance.v1',JSON.stringify(p)),preference);await page.goto('/#page=papers&days=0');const picker=page.getByLabel('模块空间目录',{exact:true});await expect(picker.locator('option')).not.toHaveCount(1);const id=await picker.locator('option').nth(1).getAttribute('value');await picker.selectOption(id!);expect((await picker.boundingBox())!.height).toBeLessThanOrEqual(44);await page.getByRole('button',{name:'阅读这篇论文',exact:true}).click();await expect(page.getByRole('dialog',{name:'论文阅读'})).toBeVisible();await page.keyboard.press('Escape');
 const note={id:'space-note',title:'空间笔记',series:'实验',content:'# My note',revision:1,archived:false,updated:'2026-09-27',backlinks:[]};await page.route('**/api/notes',r=>r.fulfill({json:[note]}));await page.route('**/api/notes/space-note',r=>r.fulfill({json:note}));await page.goto('/#page=notes');await picker.selectOption('space-note');await page.getByRole('button',{name:'定位这条记录',exact:true}).click();await expect(page.locator('.note-title')).toHaveValue('空间笔记');await page.getByRole('button',{name:'编辑',exact:true}).click();await expect(page.locator('.pavilion')).toBeHidden();
});
test('model failure preserves navigation and appearance off removes the scene',async({page})=>{
 await page.addInitScript(p=>localStorage.setItem('atlas.appearance.v1',JSON.stringify(p)),preference);await page.route('**/spatial/overview.glb',r=>r.abort());await page.goto('/#page=overview');await expect(page.locator('.pavilion-unavailable')).toBeVisible();const picker=page.getByLabel('模块空间目录',{exact:true});await picker.selectOption({index:1});await page.getByRole('button',{name:'进入这个领域',exact:true}).click();await expect(page).toHaveURL(/page=papers/);await page.goto('/#page=settings');await page.getByLabel('图谱特效',{exact:true}).selectOption('off');await expect(page.locator('.pavilion-view')).toHaveCount(0);await page.reload();await expect(page.locator('.pavilion')).toHaveCount(0);
});
test('design book exposes every module and local production assets',async({page,request})=>{
 await page.goto('/design/index.html');await expect(page.locator('article section')).toHaveCount(11);const manifest=await (await request.get('/spatial/manifest.json')).json();expect(manifest.assets.reduce((sum:number,a:{bytes:number})=>sum+a.bytes,0)).toBeLessThan(4000000);for(const asset of manifest.assets){expect((await request.get(asset.path)).ok()).toBeTruthy()}
});

test('module renderer stops when idle and survives context loss through its record directory',async({page})=>{
 await page.addInitScript(p=>localStorage.setItem('atlas.appearance.v1',JSON.stringify({...p,motion:'system'})),preference);await page.emulateMedia({reducedMotion:'no-preference'});await page.goto('/#page=overview');const stage=page.locator('.pavilion-view');await expect(stage).toHaveAttribute('data-ready','true',{timeout:15000});await page.getByRole('button',{name:'旋转模块场景',exact:true}).click();await page.waitForTimeout(2000);const frames=await stage.getAttribute('data-frames');await page.waitForTimeout(600);expect(await stage.getAttribute('data-frames')).toBe(frames);await stage.locator('canvas').evaluate(e=>(e as HTMLCanvasElement).getContext('webgl2')?.getExtension('WEBGL_lose_context')?.loseContext());await expect(page.locator('.pavilion-unavailable')).toBeVisible();await page.getByLabel('模块空间目录',{exact:true}).selectOption({index:1});await expect(page.getByRole('button',{name:'进入这个领域',exact:true})).toBeEnabled();
});


test('long paper titles keep the mobile directory and quality settings bounded',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.addInitScript(p=>localStorage.setItem('atlas.appearance.v1',JSON.stringify(p)),preference);await page.goto('/#page=papers&days=0');const picker=page.getByLabel('模块空间目录',{exact:true});await picker.selectOption({index:1});expect((await picker.boundingBox())!.height).toBeLessThanOrEqual(44);await picker.click();expect(await picker.evaluate(e=>e.matches(':open'))).toBeTruthy();await page.keyboard.press('Escape');expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);await page.goto('/#page=settings');await expect(page.getByLabel('场景画质',{exact:true})).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

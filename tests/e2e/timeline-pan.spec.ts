import {test,expect} from '@playwright/test';
for(const motion of ['system','reduced'])test(`timeline pans at maximum zoom without orbit or accidental selection (${motion})`,async({page})=>{
 await page.addInitScript(motion=>{localStorage.setItem('atlas.appearance.v1',JSON.stringify({edition:'prism',effects:'auto',motion}));sessionStorage.setItem('atlas.terminal.entered','1')},motion);
 await page.route('**/api/graph?*',r=>r.fulfill({json:{papers:[{id:'a',title:'Alpha',label:'Alpha',published:'2020-01-01'},{id:'b',title:'Beta',label:'Beta',published:'2024-01-01'}],tags:[],links:[],relations:[],total:2,truncated:false}}));
 await page.goto('/#page=map');await page.getByLabel('图谱视图',{exact:true}).selectOption('timeline');await page.getByRole('button',{name:'切换二维与三维',exact:true}).click();
 const host=page.locator('.relief-host');await host.scrollIntoViewIfNeeded();await expect(host).toHaveAttribute('data-ready','true');
 const box=(await host.boundingBox())!;
 await page.mouse.move(box.x+box.width*.7,box.y+box.height*.4);await page.mouse.wheel(0,-100);
 await expect.poll(async()=>Number(await host.getAttribute('data-zoom'))).toBeGreaterThan(1.15);
 await expect.poll(async()=>Math.abs(Number(await host.getAttribute('data-pan-x')))).toBeGreaterThan(.1);
 for(let i=0;i<6;i++)await page.getByLabel('放大数据空间',{exact:true}).click();
 await expect.poll(async()=>Number(await host.getAttribute('data-zoom'))).toBeGreaterThan(2.99);
 await host.scrollIntoViewIfNeeded();const area=(await host.boundingBox())!,before=await host.getAttribute('data-pan-x');
 await page.mouse.move(area.x+area.width*.45,area.y+80);await page.mouse.down();await page.mouse.move(area.x+area.width*.45+100,area.y+130,{steps:10});await page.mouse.up();
 await expect.poll(()=>host.getAttribute('data-pan-x')).not.toBe(before);await expect(host).toHaveAttribute('data-camera-rail','0.120');await expect(page.locator('.relief-paper')).toHaveCount(0);
 await page.getByRole('button',{name:'全览',exact:true}).click();await expect(host).toHaveAttribute('data-pan-x','0.000');await expect(host).toHaveAttribute('data-pan-y','0.000');await expect.poll(async()=>Number(await host.getAttribute('data-zoom'))).toBeLessThan(1.01);
 await host.getByRole('button',{name:'Beta',exact:true}).click();await expect(page.locator('.relief-paper')).toContainText('Beta');
});

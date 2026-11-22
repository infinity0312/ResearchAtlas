import {test,expect} from '@playwright/test';
test('PDF reading surface uses viewport height at desktop and mobile',async({page})=>{
 await page.goto('/#page=papers');await page.getByRole('button',{name:'Equivariant models for molecular prediction',exact:true}).click();await page.getByRole('button',{name:'原始 PDF',exact:true}).click();
 const reader=page.locator('.pdf-reader');await expect(reader).toBeVisible();
 for(const size of [{width:1440,height:900},{width:390,height:844}]){await page.setViewportSize(size);await expect.poll(async()=>Math.round((await reader.boundingBox())!.height)).toBe(size.height);expect(await page.locator('.pdf-page-host').evaluate(e=>e.clientHeight)).toBeGreaterThan(size.height-180)}
});
test('stationary hover survives animated tile lifting without flicker',async({page})=>{
 test.setTimeout(60000);
 await page.setViewportSize({width:800,height:700});
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
 await page.addInitScript(()=>{localStorage.setItem('atlas.appearance.v1',JSON.stringify({edition:'prism',effects:'auto',motion:'system',quality:'balanced'}));sessionStorage.setItem('atlas.terminal.entered','1')});
 const papers=[{id:'a',title:'Alpha',label:'Alpha'},{id:'b',title:'Beta',label:'Beta'}];await page.route('**/api/graph?*',r=>r.fulfill({json:{papers,tags:[{id:'t',name:'Topic',kind:'topic'}],links:papers.map(p=>({paper_id:p.id,tag_id:'t'})),relations:[],total:2,truncated:false}}));
 await page.goto('/#page=map');await page.getByLabel('图谱视图',{exact:true}).selectOption('similarity');await page.getByRole('button',{name:'切换二维与三维',exact:true}).click();const host=page.locator('.relief-host');await page.addStyleTag({content:'.relief-host{height:350px!important}'});await host.scrollIntoViewIfNeeded();await expect(host).toHaveAttribute('data-ready','true');const b=(await host.boundingBox())!;const x=b.x+b.width/2+20,y=b.y+b.height/2-20;await page.mouse.move(x,y);await expect.poll(async()=>Number(await host.getAttribute('data-hover-glow')),{timeout:20000}).toBeGreaterThan(.7);const cell=await host.getAttribute('data-hovered-cell');expect(cell).toBeTruthy();
 const samples=await host.evaluate(async(el,{x,y})=>{const samples=[];for(let i=0;i<20;i++){el.dispatchEvent(new MouseEvent('pointermove',{clientX:x+(i%2)*.2,clientY:y,bubbles:true}));await new Promise(r=>setTimeout(r,100));samples.push({cell:el.getAttribute('data-hovered-cell'),glow:Number(el.getAttribute('data-hover-glow'))})}return samples},{x,y});expect(samples.every(s=>s.cell===cell&&s.glow>.7)).toBe(true);
 expect(errors.filter(e=>/shader|WebGL|TypeError/.test(e))).toEqual([]);
});

import {test,expect} from '@playwright/test';
test('all papers form an instanced matrix, with custom range shared by 2D and 3D',async({page})=>{
 test.setTimeout(90000);
 await page.addInitScript(()=>{sessionStorage.setItem('atlas.terminal.entered','1');localStorage.setItem('atlas.appearance.v1',JSON.stringify({edition:'prism',effects:'auto',motion:'reduced'}))});
 const papers=Array.from({length:47},(_,i)=>({id:'p'+i,title:'Paper '+i,label:'P'+i,published:'2025-01-01'}));
 await page.route('**/api/graph?*',r=>r.fulfill({json:{papers,tags:[{id:'t',name:'Shared',kind:'topic'}],links:papers.map(p=>({paper_id:p.id,tag_id:'t'})),relations:[],total:47,truncated:false}}));
 await page.goto('/#page=map');await expect(page.locator('.graph-toolbar')).toContainText('47 篇文献',{timeout:15000});await expect(page.locator('.graph-view-heading')).toHaveCount(1,{timeout:15000});await expect(page.getByLabel('空间视图定位论文')).toHaveCount(0);
 await page.getByLabel('图谱视图',{exact:true}).selectOption('similarity');await page.getByRole('button',{name:'切换二维与三维',exact:true}).click();const host=page.locator('.relief-host');await host.scrollIntoViewIfNeeded();await expect(host).toHaveAttribute('data-point-count','2209');await expect(host).toHaveAttribute('data-ready','true');
 expect(Number(await host.getAttribute('data-draw-calls'))).toBeLessThan(20);await expect(page.getByLabel('三维数据定位论文')).toHaveCount(0);await expect(page.getByRole('button',{name:'下一组',exact:true})).toHaveCount(0);
 await page.locator('.matrix-range summary').click();await page.locator('.matrix-range').getByRole('button',{name:'清空',exact:true}).click();await page.getByLabel('比较论文：P0',{exact:true}).check();await page.getByLabel('比较论文：P46',{exact:true}).check();await page.getByRole('button',{name:'应用范围',exact:true}).click();await expect(host).toHaveAttribute('data-point-count','4');
 await page.getByRole('button',{name:'切换二维与三维',exact:true}).click();await expect(page.locator('.matrix-range summary')).toContainText('2 篇当前论文');await expect(page.locator('.pv-index-list button')).toHaveCount(2);
 await page.locator('.matrix-range summary').click();await page.locator('.matrix-range').getByRole('button',{name:'全选',exact:true}).click();await page.getByRole('button',{name:'应用范围',exact:true}).click();await expect(page.locator('.pv-index-list button')).toHaveCount(47);
 await page.getByLabel('图谱视图',{exact:true}).selectOption('timeline');await expect(page.locator('.graph-view-heading')).toHaveCount(1);await expect(page.locator('.paper-view-caption')).toHaveCount(0);
});


test('display range preserves population-weighted similarity',async()=>{
 const {similarityMatrix}=await import('../../web/paperViewData');
 const papers=['a','b','c'].map(id=>({id,title:id}));
 const data:any={papers,tags:[{id:'x',kind:'method'},{id:'y',kind:'method'}],links:[{paper_id:'a',tag_id:'x'},{paper_id:'a',tag_id:'y'},{paper_id:'b',tag_id:'x'},{paper_id:'c',tag_id:'x'}]};
 const subset={...data,papers:papers.slice(0,2),links:data.links.filter((l:any)=>l.paper_id!=='c')};
 expect(similarityMatrix(subset,true,data).cells.find(c=>c[0]===0&&c[1]===1)?.[2]).toBe(similarityMatrix(data).cells.find(c=>c[0]===0&&c[1]===1)?.[2]);
});

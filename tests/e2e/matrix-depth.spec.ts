import {test,expect,type Locator,type Page} from '@playwright/test';

// Sample the actual rendered canvas, not DOM overlays or the green floor.
async function coloredTiles(page:Page,canvas:Locator){
 const png=await canvas.screenshot();
 return page.evaluate(async bytes=>{
  const image=await createImageBitmap(new Blob([Uint8Array.from(bytes)],{type:'image/png'}));
  const surface=document.createElement('canvas');surface.width=image.width;surface.height=image.height;
  const context=surface.getContext('2d')!;context.drawImage(image,0,0);image.close();
  const pixels=context.getImageData(0,0,surface.width,surface.height).data;
  let colored=0;const rows=new Set<number>();
  for(let row=0;row<20;row++)for(let column=0;column<20;column++){
   const x=Math.floor(surface.width*(.2+column*.03)),y=Math.floor(surface.height*(.2+row*.03));
   const offset=(y*surface.width+x)*4,r=pixels[offset],g=pixels[offset+1],b=pixels[offset+2];
   // 100% tagged cells are saturated green; the pale floor cannot meet this test.
   if(g-r>18&&g-b>10&&r<210){colored++;rows.add(row)}
  }
  return {colored,rows:rows.size};
 },Array.from(png));
}

test('300-paper prism matrix remains rendered across overview and exact index navigation',async({page})=>{
 test.setTimeout(120000);
 await page.addInitScript(()=>{
  localStorage.setItem('atlas.appearance.v1',JSON.stringify({edition:'prism',effects:'auto',motion:'reduced',quality:'balanced'}));
  sessionStorage.setItem('atlas.terminal.entered','1');
 });
 const papers=Array.from({length:300},(_,i)=>({id:'depth-'+i,title:'Depth Matrix Paper '+i,label:'D'+i,published:'2025-01-01'}));
 const tags=[{id:'depth-tag',name:'Shared fixture classification',kind:'topic',count:300,archived:false,description:'Isolated depth regression'}];
 await page.route('**/api/graph?*',route=>route.fulfill({json:{papers,tags,links:papers.map(p=>({paper_id:p.id,tag_id:'depth-tag',source:'manual'})),relations:[],total:300,truncated:false}}));
 await page.setViewportSize({width:1440,height:1000});
 await page.goto('/#page=map');await page.getByLabel('图谱视图',{exact:true}).selectOption('similarity');await page.getByRole('button',{name:'切换二维与三维',exact:true}).click();
 const host=page.locator('.spatial-paper-view .relief-host'),canvas=host.locator('canvas');
 await host.scrollIntoViewIfNeeded();await expect(host).toHaveAttribute('data-ready','true');
 await expect(host).toHaveAttribute('data-point-count','90000');
 await expect(page.locator('.spatial-paper-view')).toHaveAttribute('data-total-papers','300');
 const depth=await host.evaluate(el=>({near:Number(el.getAttribute('data-camera-near')),far:Number(el.getAttribute('data-camera-far')),distance:Number(el.getAttribute('data-camera-distance'))}));
 expect(depth.near).toBeGreaterThan(0);expect(depth.far).toBeGreaterThan(depth.distance);
 const radius=Math.hypot(150,150);
 expect(depth.distance-depth.near).toBeGreaterThan(radius);
 expect(depth.far-depth.distance).toBeGreaterThan(radius);
 await expect.poll(()=>host.getAttribute('data-zoom')).not.toBe('1.000');
 const initial=await coloredTiles(page,canvas);expect(initial.colored).toBeGreaterThan(40);expect(initial.rows).toBeGreaterThan(8);
 await page.getByRole('button',{name:'全览',exact:true}).click();
 await host.scrollIntoViewIfNeeded();await expect(host).toHaveAttribute('data-zoom','1.000');
 const overview=await coloredTiles(page,canvas);expect(overview.colored).toBeGreaterThan(40);expect(overview.rows).toBeGreaterThan(8);
 await page.getByLabel('查找并定位相似矩阵文献',{exact:true}).fill('Depth Matrix Paper 299');
 await page.locator('.spatial-paper-view .pv-index-list button').click();
 await expect(page.locator('.relief-inspector')).toContainText('Depth Matrix Paper 299');
 await host.scrollIntoViewIfNeeded();
 await expect.poll(async()=>Number(await host.getAttribute('data-zoom'))).toBeGreaterThan(1);
 const bounds=(await host.boundingBox())!;
 let hit=false;
 for(const dx of [0,-.04,.04,-.12,.12]){
  for(const dy of [0,-.04,.04,-.12,.12]){
   await page.mouse.move(bounds.x+bounds.width*(.5+dx),bounds.y+bounds.height*(.5+dy));
   await host.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>resolve())));
   const cell=await host.getAttribute('data-hovered-cell');
   if(cell&&cell.split(',').includes('299')){hit=true;break}
  }
  if(hit)break;
 }
 expect(hit,'Index navigation must expose a real cell involving paper 299').toBeTruthy();
 await expect(host.locator('.relief-tooltip')).toContainText('Depth Matrix Paper 299');
 await expect(host).toHaveAttribute('data-point-count','90000');
});

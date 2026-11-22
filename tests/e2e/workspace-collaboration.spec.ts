import {test,expect} from '@playwright/test';
test('notes keep their heading, animate editing, manage nested folders and trash',async({page})=>{
 await page.goto('/#page=notes');
 await expect(page.getByText('从阅读到思考，让知识在笔记之间生长。')).toBeVisible();
 await page.getByRole('button',{name:'新建文件夹',exact:true}).click();
 await page.getByLabel('文件夹名称').fill('测试研究');await page.getByRole('button',{name:'创建',exact:true}).click();
 await page.getByRole('button',{name:'新建文件夹',exact:true}).click();
 await expect(page.getByText('新建于：测试研究')).toBeVisible();
 await page.getByLabel('文件夹名称').fill('推导');await page.getByRole('button',{name:'创建',exact:true}).click();
 await page.getByRole('button',{name:'新建笔记',exact:true}).click();
 await page.getByLabel('笔记标题',{exact:true}).fill('带公式的笔记');await page.locator('.cm-content').fill('# 方法\n\n$$x^2$$\n\n- [ ] 核对原文');
 await expect(page.locator('.note-toolbar [role=status]')).toHaveText('已保存',{timeout:10000});
 await expect(page.locator('.notes-workspace')).toHaveClass(/notes-editing/);
 await expect(page.locator('.cm-foldGutter')).toHaveCount(0);
 const alignment=await page.evaluate(()=>{
  const line=document.querySelector('.cm-line')!,number=Array.from(document.querySelectorAll('.cm-lineNumbers .cm-gutterElement')).find(e=>e.textContent==='1')!;
  return Math.abs(line.getBoundingClientRect().top-number.getBoundingClientRect().top);
 });expect(alignment).toBeLessThan(3);
 await page.getByRole('button',{name:'阅读',exact:true}).click();
 await expect(page.locator('.notes-workspace')).not.toHaveClass(/notes-editing/);
 await expect(page.getByText('从阅读到思考，让知识在笔记之间生长。')).toBeVisible();
 await page.getByLabel('搜索笔记',{exact:true}).fill('带公式');
 const search=await page.locator('.note-search').boundingBox(),input=await page.getByLabel('搜索笔记',{exact:true}).boundingBox();expect(input!.x+input!.width).toBeLessThanOrEqual(search!.x+search!.width);
 await page.screenshot({path:'docs/notes-workspace-reading.png',animations:'disabled'});
 await page.getByRole('button',{name:'编辑',exact:true}).click();
 await page.screenshot({path:'docs/notes-workspace-editing.png',animations:'disabled'});
 page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'删除笔记',exact:true}).click();
 await page.getByRole('button',{name:'回收站',exact:true}).click();await expect(page.locator('.notes-trash')).toContainText('带公式的笔记');
 await page.locator('.notes-trash').getByRole('button',{name:'恢复',exact:true}).click();await expect(page.locator('.notes-trash')).not.toContainText('带公式的笔记');
 for(const width of [768,390]){await page.setViewportSize({width,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy()}
});
test('collaboration draft is reviewable, publish creates note, deleted jobs vanish',async({page,request})=>{
 const h={'X-Atlas-Client':'1'};
 const w=await(await request.post('/api/collaboration',{headers:h,data:{title:'复杂推导测试',instruction:'核对公式',paper_ids:[]}})).json();
 const lease=await(await request.post(`/api/collaboration/${w.id}/claim`,{headers:h,data:{owner:'e2e'}})).json();
 await request.put(`/api/collaboration/${w.id}`,{headers:h,data:{token:lease.lease_token,revision:lease.revision,markdown:'# 审阅成果\n\n$$y=x^2$$'}});
 await page.goto('/#page=settings');await page.getByText('复杂推导测试',{exact:true}).click();await expect(page.locator('.collaboration-list .katex')).toBeVisible();
 await page.getByRole('button',{name:'确认成果 · 保存为笔记'}).click();await expect(page.locator('.collaboration-list')).toContainText('已保存为笔记');
 const jobs=await(await request.post('/api/ingest',{headers:h,data:{domain_id:'molecules',days:30}})).json();
 await page.goto('/#page=jobs');const row=page.locator('.job-row').filter({hasText:'文献同步'}).first();await row.getByRole('button',{name:'删除任务'}).click();
 await expect.poll(async()=>{const all=await(await request.get('/api/jobs')).json();return all.some((j:any)=>j.id===jobs.job_id)}).toBeFalsy();
 await page.screenshot({path:'docs/workspace-collaboration.png',animations:'disabled'});
});


test('long notes keep toolbars visible after repeated mode and viewport changes',async({page,request})=>{
 const n=await(await request.post('/api/notes',{headers:{'X-Atlas-Client':'1'},data:{title:'Long layout',series:'Layout',content:Array.from({length:50},(_,i)=>`## Section ${i}\n\nParagraph content.\n\n- one\n- two`).join('\n\n')}})).json();
 await page.goto('/#page=notes');await page.locator('.notes-file-list>button').filter({hasText:'Long layout'}).click();
 for(const width of [1440,900,1440]){
  await page.setViewportSize({width,height:1000});
  for(const mode of ['编辑','双栏','阅读']){
   await page.getByRole('button',{name:mode,exact:true}).click();await page.waitForTimeout(400);
   const b=await page.locator('.notes-workspace').boundingBox();expect(b!.height).toBeLessThan(910);
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
   const footer=await page.locator('.note-footer').boundingBox();expect(footer!.y+footer!.height).toBeLessThan(b!.y+b!.height+1);
  }
 }
 await page.screenshot({path:'docs/notes-long-layout.png'});
});

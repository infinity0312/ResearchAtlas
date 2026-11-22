import {test,expect,type APIRequestContext,type Page} from '@playwright/test';
const headers={'X-Atlas-Client':'1'};
const range={start:'2001',end:'2002',interval:'year',period:'2002'};
test.beforeEach(async({baseURL,page})=>{expect(new URL(baseURL!).port).toBe('8770');await page.addInitScript(()=>{sessionStorage.setItem('atlas.terminal.entered','1');localStorage.setItem('atlas.appearance.v1',JSON.stringify({edition:'classic',effects:'off',motion:'reduced'}))})});
async function project(request:APIRequestContext,suffix:string){const r=await request.post('/api/projects',{headers,data:{title:`隔离趋势测试-${suffix}-${Date.now()}`,scenario:'change_review',owner:'隔离测试人员',question:'新的研究线索是否需要启动同工况验证？',constraints:'界面测试，不代表科研发现',criteria:[{id:'impact',label:'判断影响'}]}});expect(r.ok()).toBeTruthy();return r.json();}
async function series(request:APIRequestContext){const rows=await(await request.get('/api/trends/series')).json();expect(rows.length).toBeGreaterThan(0);return rows[0];}
function trendHref(id:string,scope=range){return '/#'+new URLSearchParams({page:'trends',trend_id:id,trend_start:scope.start,trend_end:scope.end,trend_interval:scope.interval,trend_period:scope.period})}
async function preview(request:APIRequestContext,id:string){const r=await request.get('/api/projects/trend-preview?'+new URLSearchParams({series_id:id,...range}));expect(r.ok()).toBeTruthy();return r.json();}
async function detail(request:APIRequestContext,id:string){return (await request.get(`/api/projects/${id}`)).json();}
async function capture(page:Page,pid:string,reason:string){await page.getByRole('button',{name:'转为项目线索',exact:true}).first().click();const modal=page.getByRole('dialog',{name:'保存趋势线索',exact:true});await modal.getByLabel('目标项目',{exact:true}).selectOption(pid);await modal.getByLabel('关注理由',{exact:true}).fill(reason);return modal;}

test('real empty direction freezes missing counts, deduplicates and restores the precise trend scope',async({page,request})=>{
 const p=await project(request,'empty'),s=await series(request),original=await preview(request,s.id);
 expect(original.snapshot.points).toHaveLength(2);expect(original.snapshot.points.every((point:any)=>point.count===null)).toBe(true);
 await page.goto(trendHref(s.id));const modal=await capture(page,p.id,'虽然计数未获取，仍需保留此方向的核查计划');await expect(modal.locator('.trend-capture-scope')).toContainText('2001');await expect(modal.locator('.trend-capture-body')).toHaveAttribute('data-source-key',original.source_key);
 await modal.getByRole('button',{name:'保存项目线索',exact:true}).click();await expect(modal.getByRole('link',{name:'前往项目处理',exact:true})).toBeVisible();const list=await(await request.get(`/api/projects/${p.id}/trend-leads`)).json();expect(list.items).toHaveLength(1);const lead=list.items[0];expect(lead.snapshot.points).toEqual(original.snapshot.points);expect(lead.snapshot.scope).toEqual(original.snapshot.scope);
 const repeat=await request.post(`/api/projects/${p.id}/trend-leads`,{headers,data:{series_id:s.id,...range,source_key:original.source_key,reason:'重复操作不得覆盖原来的关注理由',paper_ids:[]}});expect(repeat.ok()).toBeTruthy();expect((await repeat.json()).reason).toBe(lead.reason);
 await modal.getByRole('link',{name:'前往项目处理',exact:true}).click();const row=page.locator(`[data-trend-lead-id="${lead.id}"]`);await expect(row).toBeVisible();await page.reload();await expect(row).toBeVisible();await row.getByText('查看记录时的计数与周期状态',{exact:true}).click();await expect(row.locator('.project-trend-counts')).toContainText('未获取');
 await row.getByRole('button',{name:'回看当前趋势',exact:true}).click();await expect(page).toHaveURL(/trend_start=2001/);await expect(page).toHaveURL(/trend_end=2002/);await expect(page).toHaveURL(/trend_period=2002/);await page.reload();await expect(page.getByLabel('趋势开始时间')).toHaveValue('2001');await expect(page.getByLabel('趋势结束时间')).toHaveValue('2002');
 const d=await detail(request,p.id);expect(d.project.revision).toBe(p.revision);expect(d.evidence).toHaveLength(0);expect(d.readiness.can_review).toBe(false);
});

test('real trend lead conflict preserves local judgement and does not change scientific decision revision',async({page,request})=>{
 const p=await project(request,'conflict'),s=await series(request),source=await preview(request,s.id);const root=`/api/projects/${p.id}/trend-leads`;
 const created=await request.post(root,{headers,data:{series_id:s.id,...range,source_key:source.source_key,reason:'最初关注理由仅为待研究方向',paper_ids:[]}});expect(created.ok()).toBeTruthy();const lead=await created.json();
 const invalid=await request.post(root,{headers,data:{series_id:s.id,...range,source_key:'0'.repeat(64),reason:'来源改变时不能保存旧预览',paper_ids:[]}});expect(invalid.status()).toBe(409);
 await page.goto(`/#page=projects&project_id=${p.id}&trend_lead_id=${lead.id}`);const row=page.locator(`[data-trend-lead-id="${lead.id}"]`),reason=row.getByRole('textbox'),save=row.getByRole('button',{name:'保存趋势取舍',exact:true});await reason.fill('本机保留判断与待验证条件不可被覆盖');await row.getByRole('combobox').selectOption('kept');
 const remote=await request.put(`${root}/${lead.id}`,{headers,data:{revision:lead.revision,status:'excluded',reason:'远端已排除，需要核对不同的检索工况'}});expect(remote.ok()).toBeTruthy();const updated=await remote.json();
 const conflict=page.waitForResponse(r=>r.request().method()==='PUT'&&new URL(r.url()).pathname===`${root}/${lead.id}`&&r.status()===409);await save.click();await conflict;await expect(reason).toHaveValue('本机保留判断与待验证条件不可被覆盖');await expect(row).toContainText('远端已排除，需要核对不同的检索工况');await expect(save).toBeDisabled();
 await row.getByRole('button',{name:'按最新修订继续编辑趋势线索',exact:true}).click();const savedResponse=page.waitForResponse(r=>r.request().method()==='PUT'&&new URL(r.url()).pathname===`${root}/${lead.id}`&&r.status()===200);await save.click();await savedResponse;await expect(save).toBeDisabled();const result=await(await request.get(root)).json();expect(result.items[0]).toMatchObject({status:'kept',revision:updated.revision+1,reason:'本机保留判断与待验证条件不可被覆盖'});expect(result.items[0].snapshot).toEqual(lead.snapshot);expect((await detail(request,p.id)).project.revision).toBe(p.revision);
});

// Rich sample fixtures test UI selection and payloads only. They do not claim
// that a mocked POST exercises server freezing/eligibility (backend tests do).
async function richFixture(page:Page,p:any){
 const sample=(id:string,title:string,local:number|null,relevant=true)=>({id,title,quote:`冻结原文片段-${id}`,bottleneck:'隔离夹具瓶颈',relevant,local_version:local,local_title:local?title:null});
 const snapshot:any={version:1,series_id:'qa-rich',name:'隔离趋势方向',query:'ti:fixture',scope:{...range},focus_paper_id:null,source:'隔离数据源',date_basis:'首次提交时间 UTC',points:[{period:'2001',count:null,partial:false,fetched:null,source:null},{period:'2002',count:12,partial:false,fetched:null,source:'fixture'}],growth:null,signal:{x:null,y:null,status:'样本夹具',rebound:false,coordinate_basis:'direction_overview'},papers:[sample('2609.00000','本地样本甲',1),sample('2609.00001','本地样本乙',1),sample('9999.00001','外部样本',null),sample('2609.00002','范围外样本',1,false)]};
 let revision=1,latestQuote=false,saved:any=null;const posts:any[]=[];
 await page.route(`**/api/projects/${p.id}/trend-leads/qa-lead/intakes`,route=>{
  if(route.request().method()!=='GET')return route.abort('blockedbyclient');
  return route.fulfill({json:{items:[],capabilities:{analysis_enabled:false,analysis_blocker:'隔离夹具不启动收录或模型',runner_paused:false}}});
 });
 await page.route('**/api/trends/series',r=>r.fulfill({json:[{id:'qa-rich',name:snapshot.name,query:snapshot.query,color:'#327c72',domain_id:'molecules',is_root:true,aliases:[]}]}));
 await page.route('**/api/trends/data?*',r=>{const u=new URL(r.request().url()),start=u.searchParams.get('start')!;return r.fulfill({json:{series:[{id:'qa-rich',name:snapshot.name,query:snapshot.query,color:'#327c72',growth:null,points:snapshot.points.map((point:any)=>({...point,period:point.period==='2001'?start:point.period})),insight:{x:null,y:null,growth:null,acceleration:null,rebound:false,status:'待核查',periods:[{period:'2002',sample:4,population:12,opportunity:null,papers:snapshot.papers}]}}]}})});
 await page.route('**/api/projects/trend-preview?*',r=>{const u=new URL(r.request().url());return r.fulfill({json:{source_key:String(u.searchParams.has('paper_id')?3:revision).repeat(64),snapshot:{...snapshot,focus_paper_id:u.searchParams.get('paper_id'),scope:{start:u.searchParams.get('start'),end:u.searchParams.get('end'),interval:u.searchParams.get('interval'),period:u.searchParams.get('period')||'2002'},papers:snapshot.papers.map((paper:any)=>({...paper,quote:latestQuote?'新来源片段，不得覆盖旧记录':paper.quote}))}}})});
 await page.route(`**/api/projects/${p.id}/trend-leads`,async r=>{if(r.request().method()==='POST'){const body=r.request().postDataJSON();posts.push(body);saved={id:'qa-lead',project_id:p.id,source_key:body.source_key,snapshot:{...structuredClone(snapshot),focus_paper_id:body.focus_paper_id||null,scope:{start:body.start,end:body.end,interval:body.interval,period:body.period||'2002'}},reason:body.reason,status:'pending',revision:1,candidate_ids:body.paper_ids.map((id:string)=>({paper_id:id,candidate_id:'candidate-'+id})),created:new Date().toISOString(),updated:new Date().toISOString(),source_changed:false,current_source_available:true};return r.fulfill({json:saved})}return r.fulfill({json:{items:saved?[{...saved,source_changed:latestQuote}]:[],total:saved?1:0}})});
 return {snapshot,posts,change:()=>{revision=2;latestQuote=true}};
}

test('rich UI selects multiple eligible local samples, excludes external samples and keeps frozen quotations',async({page,request})=>{
 const p=await project(request,'rich-ui'),fixture=await richFixture(page,p);await page.goto(trendHref('qa-rich'));const modal=await capture(page,p.id,'两篇本地方法值得进入候选池核查');
 await modal.getByRole('checkbox',{name:'同时加入论文候选：本地样本甲',exact:true}).check();await modal.getByRole('checkbox',{name:'同时加入论文候选：本地样本乙',exact:true}).check();
 for(const title of ['外部样本','范围外样本']){const box=modal.getByRole('checkbox',{name:'同时加入论文候选：'+title,exact:true});if(await box.count())await expect(box).toBeDisabled();}
 await modal.getByRole('button',{name:'保存项目线索',exact:true}).click();await expect(modal.getByRole('link',{name:'前往项目处理',exact:true})).toBeVisible();expect(fixture.posts).toHaveLength(1);expect([...fixture.posts[0].paper_ids].sort()).toEqual(['2609.00000','2609.00001']);expect(fixture.posts[0]).toMatchObject({series_id:'qa-rich',start:range.start,end:range.end,interval:range.interval,source_key:'1'.repeat(64)});
 fixture.change();await modal.getByRole('link',{name:'前往项目处理',exact:true}).click();const row=page.locator('[data-trend-lead-id="qa-lead"]');await expect(row).toBeVisible();await row.getByText('查看原文片段与出处',{exact:true}).first().click();await expect(row).toContainText('冻结原文片段-2609.00000');await expect(row).not.toContainText('新来源片段，不得覆盖旧记录');
});

test('390px reduced-motion browsing and capture Escape remain read only',async({page,request},testInfo)=>{
 const p=await project(request,'mobile-ui');await richFixture(page,p);await page.setViewportSize({width:390,height:844});await page.emulateMedia({reducedMotion:'reduce'});const writes:string[]=[];page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/api/')&&!['GET','HEAD'].includes(r.method()))writes.push(r.method()+' '+r.url())});
 await page.goto(trendHref('qa-rich'));const modal=await capture(page,p.id,'移动端只浏览，不提交任何项目判断');await expect(modal.locator('.trend-capture-body')).toHaveAttribute('data-source-key','1'.repeat(64));expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await page.screenshot({path:testInfo.outputPath('isolated-trend-capture-mobile.png')});await page.keyboard.press('Escape');await expect(modal).not.toBeVisible();await expect(page.getByRole('button',{name:'转为项目线索',exact:true}).first()).toBeVisible();expect(writes).toEqual([]);
});

test('changing the displayed range disables placeholder capture and saves only the refreshed scope',async({page,request})=>{
 const p=await project(request,'scope-ui');const fixture=await richFixture(page,p);await page.goto(trendHref('qa-rich'));await expect(page.getByRole('button',{name:'转为项目线索',exact:true}).first()).toBeEnabled();
 let release!:()=>void,started!:()=>void;const gate=new Promise<void>(resolve=>{release=resolve}),pending=new Promise<void>(resolve=>{started=resolve});
 await page.route('**/api/trends/data?*',async route=>{if(new URL(route.request().url()).searchParams.get('end')!=='2003')return route.fallback();started();await gate;return route.fulfill({json:{series:[{id:'qa-rich',name:'隔离趋势方向',query:'ti:fixture',color:'#327c72',growth:null,points:[{period:'2001',count:null,partial:false},{period:'2002',count:12,partial:false},{period:'2003',count:null,partial:false}],insight:{x:null,y:null,growth:null,acceleration:null,rebound:false,status:'待核查',periods:[]}}]}})});
 try{await page.getByLabel('趋势结束时间',{exact:true}).fill('2003');await pending;await expect(page.getByRole('button',{name:'转为项目线索',exact:true}).first()).toBeDisabled();}finally{release();}
 await expect(page.getByRole('button',{name:'转为项目线索',exact:true}).first()).toBeEnabled();const modal=await capture(page,p.id,'仅保存新的完整展示范围，不混合旧数据');await expect(modal.locator('.trend-capture-scope')).toContainText('2003');await modal.getByRole('button',{name:'保存项目线索',exact:true}).click();await expect(modal.getByRole('link',{name:'前往项目处理',exact:true})).toBeVisible();expect(fixture.posts).toHaveLength(1);expect(fixture.posts[0]).toMatchObject({series_id:'qa-rich',start:'2001',end:'2003',interval:'year'});
});

test('a changed source rejected during capture preserves the judgement instead of silently retrying',async({page,request})=>{
 const p=await project(request,'source-race');await richFixture(page,p);let attempts=0;
 await page.route(`**/api/projects/${p.id}/trend-leads`,route=>{if(route.request().method()!=='POST')return route.fallback();attempts++;return route.fulfill({status:409,json:{detail:'趋势来源已变化，请保留输入并重新预览'}})});
 await page.goto(trendHref('qa-rich'));const reason='来源变化时需要我重新确认的关注理由',modal=await capture(page,p.id,reason);await modal.getByRole('button',{name:'保存项目线索',exact:true}).click();await expect(modal.getByRole('alert')).toContainText('来源已变化');await expect(modal.getByLabel('关注理由',{exact:true})).toHaveValue(reason);expect(attempts).toBe(1);
});

for(const external of [false,true])test(`${external?'external':'local'} sample capture freezes its focus and never silently broadens candidate selection`,async({page,request})=>{
 const p=await project(request,external?'external-focus':'local-focus'),fixture=await richFixture(page,p);await page.goto(trendHref('qa-rich'));
 await page.getByRole('button',{name:'跨期变化与论文依据',exact:true}).click();const sample=page.locator('.signal-source-card').filter({hasText:external?'外部样本':'本地样本甲'});await sample.getByRole('button',{name:'加入项目线索',exact:true}).click();
 const modal=page.getByRole('dialog',{name:'保存趋势线索',exact:true});await expect(modal.locator('.trend-capture-body')).toHaveAttribute('data-source-key','3'.repeat(64));await expect(modal.locator('.trend-capture-heading')).toContainText(external?'外部样本':'本地样本甲');await modal.getByLabel('目标项目',{exact:true}).selectOption(p.id);await modal.getByLabel('关注理由',{exact:true}).fill('仅记录所选样本与当前研究问题的关联');
 if(external){await expect(modal.getByRole('checkbox',{name:'同时加入论文候选：外部样本',exact:true})).toHaveCount(0);await expect(modal).toContainText('不创建论文候选');}else await expect(modal.getByRole('checkbox',{name:'同时加入论文候选：本地样本甲',exact:true})).toBeChecked();
 await modal.getByRole('button',{name:'保存项目线索',exact:true}).click();await expect(modal.getByRole('link',{name:'前往项目处理',exact:true})).toBeVisible();expect(fixture.posts).toHaveLength(1);expect(fixture.posts[0]).toMatchObject({focus_paper_id:external?'9999.00001':'2609.00000',period:'2002',source_key:'3'.repeat(64)});expect(fixture.posts[0].paper_ids).toEqual(external?[]:['2609.00000']);
});

test('a historical source period missing from the current samples is disclosed before a new paper capture',async({page,request})=>{
 const p=await project(request,'missing-period'),fixture=await richFixture(page,p);
 await page.goto(trendHref('qa-rich',{...range,period:'2001'}));
 const report=page.getByRole('region',{name:'跨期变化与论文依据',exact:true});
 await expect(report.getByRole('status')).toContainText('记录的来源周期 2001 不在当前可展示的样本中');
 await expect(page.getByLabel('查看论文依据周期',{exact:true})).toHaveValue('2002');
 await report.locator('.signal-source-card').filter({hasText:'本地样本甲'}).getByRole('button',{name:'加入项目线索',exact:true}).click();
 const modal=page.getByRole('dialog',{name:'保存趋势线索',exact:true});
 await expect(modal.locator('.trend-capture-scope')).toContainText('来源周期 2002');
 expect(fixture.posts).toHaveLength(0);
});

import {test,expect,type APIRequestContext,type Page} from '@playwright/test';
const headers={'X-Atlas-Client':'1'},paperId='2609.00000',leadId='qa-intake-lead';
test.beforeEach(async({baseURL,page})=>{expect(new URL(baseURL!).port).toBe('8770');await page.addInitScript(()=>{sessionStorage.setItem('atlas.terminal.entered','1');localStorage.setItem('atlas.appearance.v1',JSON.stringify({edition:'classic',motion:'reduced',effects:'off'}))})});
async function project(request:APIRequestContext,label:string){const r=await request.post('/api/projects',{headers,data:{title:`隔离收录测试-${label}-${Date.now()}`,scenario:'change_review',owner:'隔离测试人员',question:'是否将来源样本收录后再核查适用性？',constraints:'界面夹具，不代表实际下载成果',criteria:[{id:'impact',label:'判断影响'}]}});expect(r.ok()).toBeTruthy();return r.json();}

// Only the intake state projection is mocked here. Worker execution, PDF hashes,
// official-source validation and shared-job identity belong to backend tests.
async function fixture(page:Page,p:any,{enabled=false,initial=null}:{enabled?:boolean;initial?:any}={}){
 const now=new Date().toISOString();const frozen={version:1,series_id:'qa-intake-series',name:'隔离收录方向',query:'ti:fixture',focus_paper_id:paperId,scope:{start:'2001',end:'2002',interval:'year',period:'2002'},source:'隔离快照来源',date_basis:'首次提交时间 UTC',points:[{period:'2002',count:null,partial:false,fetched:null,source:null}],growth:null,signal:{x:null,y:null,status:'待核查',rebound:false},papers:[{id:paperId,title:'加入时的样本题名',quote:'原始冻结引文必须保留',bottleneck:'先收录再核查工况',relevant:true,local_version:null,local_title:null}]};
 const lead:any={id:leadId,project_id:p.id,source_key:'a'.repeat(64),snapshot:frozen,reason:'原始关注理由不能被下载结果覆盖',status:'pending',revision:1,candidate_ids:[],created:now,updated:now,source_changed:false,current_source_available:true};
 let item:any=initial,conflict=false,hold:Promise<void>|null=null;const posts:{path:string;body:any}[]=[];
 const base={id:'qa-intake',project_id:p.id,lead_id:leadId,paper_id:paperId,domain_id:'molecules',revision:1,status:'queued',analysis_requested:false,analysis_status:'not_requested',analysis_blocker:null,actual_version:null,metadata_version:null,metadata_snapshot:{},judgment_snapshot:{},pdf_sha256:null,pdf_version:null,pdf_ready:false,pdf_pages:null,paper_title:'',candidate_id:null,analysis_id:null,download_job_id:'qa-download',analysis_job_id:null,created:now,updated:now};
 const endpoint=`/api/projects/${p.id}/trend-leads/${leadId}/intakes`;
 await page.route(`**/api/projects/${p.id}/trend-leads`,r=>r.fulfill({json:{items:[lead],total:1}}));
 await page.route(`**${endpoint}**`,async r=>{const req=r.request(),path=new URL(req.url()).pathname;if(req.method()==='GET')return r.fulfill({json:{items:item?[item]:[],capabilities:{analysis_enabled:enabled,analysis_blocker:enabled?null:'模型调用已关闭',runner_paused:false}}});const body=req.postDataJSON();posts.push({path,body});if(hold)await hold;if(conflict){conflict=false;lead.revision++;return r.fulfill({status:409,json:{detail:'收录记录已变化，请核对最新修订'}})}if(path.endsWith('/retry'))item={...item,status:'queued',revision:item.revision+1};else if(path.endsWith('/analysis'))item={...item,analysis_requested:true,analysis_status:enabled?'queued':'blocked',revision:item.revision+1};else item=item||{...base,domain_id:body.domain_id,analysis_requested:body.analyze};return r.fulfill({json:item});});
 return {posts,endpoint,lead,base,set:(next:any)=>{item=next},conflict:()=>{conflict=true},hold:(gate:Promise<void>|null)=>{hold=gate}};
}
async function open(page:Page,pid:string){await page.goto(`/#page=projects&project_id=${pid}&trend_lead_id=${leadId}`);const row=page.locator(`[data-trend-lead-id="${leadId}"]`);await expect(row).toBeVisible();return row.locator(`[data-intake-paper-id="${paperId}"]`);}

test('real isolated enqueue deduplicates the download without running the network worker or enabling models',async({page,request})=>{
 const p=await project(request,'real-enqueue'),external='2609.09999';const params=new URLSearchParams({series_id:'qa-intake',start:'2025',end:'2025',interval:'year',period:'2025',paper_id:external});
 const previewResponse=await request.get('/api/projects/trend-preview?'+params);expect(previewResponse.ok()).toBeTruthy();const preview=await previewResponse.json();expect(preview.snapshot.papers.some((paper:any)=>paper.id===external&&paper.local_version===null)).toBe(true);
 const leadResponse=await request.post(`/api/projects/${p.id}/trend-leads`,{headers,data:{series_id:'qa-intake',start:'2025',end:'2025',interval:'year',period:'2025',focus_paper_id:external,source_key:preview.source_key,reason:'隔离外部样本只安排下载，不运行网络或模型',paper_ids:[]}});expect(leadResponse.ok()).toBeTruthy();const lead=await leadResponse.json(),endpoint=`/api/projects/${p.id}/trend-leads/${lead.id}/intakes`;
 const before=await(await request.get(endpoint)).json();expect(before.items).toHaveLength(0);expect(before.capabilities.analysis_enabled).toBe(false);const control=await(await request.get('/api/model-control')).json();
 const stale=await request.post(endpoint,{headers,data:{revision:lead.revision+1,paper_id:external,domain_id:'molecules',analyze:false}});expect(stale.status()).toBe(409);
 const body={revision:lead.revision,paper_id:external,domain_id:'molecules',analyze:false};const created=await request.post(endpoint,{headers,data:body});expect(created.ok()).toBeTruthy();const intake=await created.json();expect(intake.download_job_id).toBeTruthy();expect(intake.analysis_requested).toBe(false);expect(intake.analysis_id).toBeNull();expect(intake.pdf_ready).toBe(false);
 const duplicate=await request.post(endpoint,{headers,data:body});expect(duplicate.ok()).toBeTruthy();expect(await duplicate.json()).toMatchObject({id:intake.id,download_job_id:intake.download_job_id});const listed=await(await request.get(endpoint)).json();expect(listed.items).toHaveLength(1);
 const wrong=await request.get(`/api/projects/${p.id}/trend-leads/not-this-lead/intakes`);expect(wrong.status()).toBe(404);
 const writes:string[]=[];page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/api/')&&!['GET','HEAD'].includes(r.method()))writes.push(r.method()+' '+r.url())});await page.goto(`/#page=projects&project_id=${p.id}&trend_lead_id=${lead.id}`);await expect(page.locator(`[data-intake-paper-id="${external}"]`).getByRole('status')).toContainText('PDF：');expect(writes).toEqual([]);
 const after=await(await request.get(`/api/projects/${p.id}/trend-leads`)).json();expect(after.items[0].snapshot).toEqual(lead.snapshot);expect(after.items[0].reason).toBe(lead.reason);expect((await(await request.get(`/api/projects/${p.id}`)).json()).project.revision).toBe(p.revision);expect(await(await request.get('/api/model-control')).json()).toEqual(control);
});

test('model-off intake submits only an explicit download and suppresses duplicate active actions',async({page,request})=>{
 const p=await project(request,'off'),f=await fixture(page,p);const writes:string[]=[];page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/api/')&&!['GET','HEAD'].includes(r.method()))writes.push(new URL(r.url()).pathname)});
 const intake=await open(page,p.id);expect(f.posts).toHaveLength(0);await intake.getByRole('button',{name:'收录并下载',exact:true}).click();await intake.getByLabel('收录领域',{exact:true}).selectOption('molecules');await expect(intake.getByRole('checkbox',{name:'下载后全文分析',exact:true})).toBeDisabled();
 let release!:()=>void;const gate=new Promise<void>(resolve=>{release=resolve});f.hold(gate);const submit=intake.getByRole('button',{name:'确认收录并下载',exact:true});try{await submit.click();await expect(intake.getByRole('button',{name:'正在提交…',exact:true})).toBeDisabled();await expect.poll(()=>f.posts.length).toBe(1);}finally{release();f.hold(null);}
 await expect(intake.getByRole('status')).toContainText('PDF：排队中');await expect(intake.getByRole('button',{name:'收录并下载',exact:true})).toHaveCount(0);expect(f.posts[0].body).toEqual({revision:1,paper_id:paperId,domain_id:'molecules',analyze:false});expect(writes).toEqual([f.endpoint]);expect(writes.some(path=>/settings|model-control|analyze/.test(path))).toBe(false);
});

test('completed metadata and PDF stay separate from frozen quotation and candidate links survive refresh',async({page,request})=>{
 const p=await project(request,'complete');const candidateResponse=await request.post(`/api/projects/${p.id}/candidates`,{headers,data:{paper_id:paperId,reason:'隔离收录完成后的候选关联'}});expect(candidateResponse.ok()).toBeTruthy();const candidate=await candidateResponse.json();
 const f=await fixture(page,p);f.set({...f.base,status:'done',revision:2,actual_version:2,metadata_version:2,metadata_snapshot:{version:2,title:'官方元数据更新后的题名'},pdf_version:2,pdf_ready:true,pdf_pages:7,paper_title:'官方元数据更新后的题名',candidate_id:candidate.id,analysis_status:'blocked',analysis_requested:true,analysis_blocker:'模型调用已关闭'});
 const intake=await open(page,p.id);await expect(intake).toContainText('元数据记录 v2');await expect(intake).toContainText('PDF v2');await expect(intake).toContainText('7 页');await expect(intake.getByRole('status')).toContainText('全文分析：暂不可分析');await expect(intake.getByRole('button',{name:'开始全文分析',exact:true})).toBeDisabled();
 const row=page.locator(`[data-trend-lead-id="${leadId}"]`);await row.getByText('查看原文片段与出处',{exact:true}).first().click();await expect(row).toContainText('原始冻结引文必须保留');await expect(row).toContainText('原始关注理由不能被下载结果覆盖');expect(f.lead.snapshot.papers[0].local_version).toBeNull();
 await expect(intake.getByRole('link',{name:'打开此次版本 PDF',exact:false})).toHaveAttribute('href',/version=2/);await intake.getByRole('button',{name:'查看论文候选',exact:true}).click();await expect(page).toHaveURL(new RegExp(`candidate_id=${candidate.id}`));await page.reload();await expect(page.locator(`[data-candidate-id="${candidate.id}"]`)).toBeVisible();expect(f.posts).toEqual([]);
});

test('completion polling refreshes the original projects candidate list before navigating',async({page,request})=>{
 const p=await project(request,'completion-poll'),f=await fixture(page,p);
 f.set({...f.base,status:'queued'});
 const intake=await open(page,p.id);
 await expect(page.getByText('暂无候选论文。',{exact:false})).toBeVisible();
 const response=await request.post(`/api/projects/${p.id}/candidates`,{headers,data:{paper_id:paperId,reason:'异步收录完成后关联回原项目'}});expect(response.ok()).toBeTruthy();const candidate=await response.json();
 f.set({...f.base,revision:2,status:'done',actual_version:1,pdf_version:1,pdf_ready:true,pdf_pages:2,candidate_id:candidate.id});
 await expect(intake.getByRole('status')).toContainText('PDF：可阅读',{timeout:10000});
 await intake.getByRole('button',{name:'查看论文候选',exact:true}).click();
 await expect(page.locator(`[data-candidate-id="${candidate.id}"]`)).toBeVisible();
 expect(f.posts).toEqual([]);
});

test('download completion does not mark blocked, partial or waiting analysis as completed',async({page,request})=>{
 const p=await project(request,'partial'),f=await fixture(page,p,{enabled:true});f.set({...f.base,status:'done',actual_version:1,pdf_version:1,pdf_ready:true,pdf_pages:2,analysis_requested:true,analysis_status:'blocked',analysis_blocker:'分段分析未完成，请核对任务',download_job_status:'done',analysis_job_status:'done',analysis_id:null});
 const intake=await open(page,p.id);await expect(intake.getByRole('status')).toContainText('PDF：可阅读');await expect(intake.getByRole('status')).toContainText('全文分析：暂不可分析');await expect(intake).toContainText('分段分析未完成');await expect(intake).not.toContainText('全文分析：已完成');expect(f.posts).toEqual([]);
 f.set({...f.base,status:'paused',analysis_status:'paused'});await intake.getByRole('button',{name:'刷新收录状态',exact:true}).click();await expect(intake).toContainText('不会自动恢复旧任务');await expect(intake.getByRole('button',{name:'重试收录下载',exact:true})).toHaveCount(0);expect(f.posts).toEqual([]);
});

test('409 keeps domain and analysis choices until an explicit revision acknowledgement',async({page,request})=>{
 const p=await project(request,'conflict'),f=await fixture(page,p,{enabled:true});const intake=await open(page,p.id);await intake.getByRole('button',{name:'收录并下载',exact:true}).click();await intake.getByLabel('收录领域',{exact:true}).selectOption('life');await intake.getByRole('checkbox',{name:'下载后全文分析',exact:true}).check();f.conflict();await intake.getByRole('button',{name:'确认收录并下载',exact:true}).click();await expect(intake.getByRole('alert')).toContainText('当前选择已保留');await expect(intake.getByLabel('收录领域',{exact:true})).toHaveValue('life');await expect(intake.getByRole('checkbox',{name:'下载后全文分析',exact:true})).toBeChecked();await expect(intake.getByRole('button',{name:'确认收录并下载',exact:true})).toBeDisabled();expect(f.posts).toHaveLength(1);
 await intake.getByRole('button',{name:'采用最新收录修订',exact:true}).click();await intake.getByRole('button',{name:'确认收录并下载',exact:true}).click();await expect(intake.getByRole('status')).toContainText('PDF：排队中');expect(f.posts).toHaveLength(2);expect(f.posts[1].body).toMatchObject({revision:2,domain_id:'life',analyze:true});
});

test('failed download retry reuses its task and mobile keyboard close restores the intake trigger',async({page,request},testInfo)=>{
 const p=await project(request,'mobile'),f=await fixture(page,p);await page.setViewportSize({width:390,height:844});await page.emulateMedia({reducedMotion:'reduce'});const intake=await open(page,p.id),trigger=intake.getByRole('button',{name:'收录并下载',exact:true});await trigger.focus();await page.keyboard.press('Enter');await expect(intake.getByLabel('收录领域',{exact:true})).toBeFocused();await page.keyboard.press('Escape');await expect(trigger).toBeFocused();await expect(page.locator(`[data-trend-lead-id="${leadId}"]`)).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();expect(f.posts).toEqual([]);
 f.set({...f.base,status:'failed',revision:3});await page.reload();const reloaded=page.locator(`[data-intake-paper-id="${paperId}"]`);await expect(reloaded.getByRole('button',{name:'重试收录下载',exact:true})).toBeVisible();await reloaded.getByRole('button',{name:'重试收录下载',exact:true}).click();await expect(reloaded.getByRole('status')).toContainText('PDF：排队中');expect(f.posts).toHaveLength(1);expect(f.posts[0]).toEqual({path:f.endpoint+'/qa-intake/retry',body:{revision:3}});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await page.screenshot({path:testInfo.outputPath('isolated-intake-mobile.png')});
});

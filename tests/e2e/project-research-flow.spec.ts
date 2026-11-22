import {test,expect,type APIRequestContext,type Page} from '@playwright/test';

// These flows write only to tests.serve's temporary database. Never point them at
// the user's local 8765 library, even when an external server is already running.
test.beforeEach(async({page,baseURL})=>{
 expect(new URL(baseURL!).port).toBe('8770');
 await page.addInitScript(()=>{sessionStorage.setItem('atlas.terminal.entered','1');localStorage.setItem('atlas.appearance.v1',JSON.stringify({edition:'classic',motion:'reduced',effects:'off'}))});
});
const headers={'X-Atlas-Client':'1'};
const paperId='2609.00000';
async function createProject(request:APIRequestContext,label:string){
 const response=await request.post('/api/projects',{headers,data:{title:`研究闭环测试-${label}-${Date.now()}`,scenario:'route_review',owner:'隔离测试人员',question:'在相同工况下应采用哪一条研发路线？',constraints:'只使用隔离夹具，不代表科学结论',criteria:[{id:'performance',label:'性能测试标准'},{id:'risk',label:'风险测试标准'}]}});
 expect(response.ok()).toBeTruthy();return response.json();
}
async function projectDetail(request:APIRequestContext,id:string){const response=await request.get(`/api/projects/${id}`);expect(response.ok()).toBeTruthy();return response.json();}
async function addFromPaper(page:Page,projectId:string,reason:string,reader=false){
 await page.goto('/#page=papers&days=0');
 const row=page.locator(`[data-paper-id="${paperId}"]`);
 if(reader)await row.locator('.paper-title').click();else await row.getByRole('button',{name:'摘要与分析概要',exact:true}).click();
 const scope=reader?page.getByRole('dialog',{name:'论文阅读',exact:true}):row;
 await scope.getByRole('button',{name:'加入项目线索',exact:true}).click();
 const dialog=page.getByRole('dialog',{name:'加入项目线索',exact:true});
 await dialog.getByLabel('目标项目',{exact:true}).selectOption(projectId);
 await dialog.getByLabel('关联原因',{exact:true}).fill(reason);
 await dialog.getByRole('button',{name:'确认加入线索',exact:true}).click();
 await expect(dialog.getByRole('link',{name:'前往项目处理',exact:true})).toBeVisible();
 return dialog;
}

for(const reader of [false,true])test(`${reader?'reader':'inline summary'} adds a candidate and opens a refreshable project deep link`,async({page,request})=>{
 const project=await createProject(request,reader?'reader':'inline');const reason='同工况方法值得纳入比较，尚不构成有效证据';
 const dialog=await addFromPaper(page,project.id,reason,reader);
 const result=await request.get(`/api/projects/${project.id}/candidates`);const {items}=await result.json();expect(items).toHaveLength(1);const candidate=items[0];
 expect(candidate.paper_id).toBe(paperId);expect(candidate.reason).toBe(reason);expect(candidate.status).toBe('pending');
 expect((await projectDetail(request,project.id)).project.revision).toBe(project.revision);
 await dialog.getByRole('link',{name:'前往项目处理',exact:true}).click();
 await expect(page).toHaveURL(new RegExp(`project_id=${project.id}.*candidate_id=${candidate.id}|candidate_id=${candidate.id}.*project_id=${project.id}`));
 await expect(page.locator(`[data-candidate-id="${candidate.id}"]`)).toBeVisible();
 await page.reload();await expect(page.locator(`[data-candidate-id="${candidate.id}"]`)).toBeVisible();
 expect(new URLSearchParams(new URL(page.url()).hash.slice(1)).get('candidate_id')).toBe(candidate.id);
});

test('candidate selection persists reasons without changing decision revision and links back from the reader',async({page,request})=>{
 const project=await createProject(request,'candidate-ui');
 const created=await request.post(`/api/projects/${project.id}/candidates`,{headers,data:{paper_id:paperId,reason:'初始筛选理由仅用于测试'}});const candidate=await created.json();
 await page.goto(`/#page=projects&project_id=${project.id}&candidate_id=${candidate.id}`);
 const row=page.locator(`[data-candidate-id="${candidate.id}"]`);
 await row.getByRole('combobox').selectOption('kept');await row.getByRole('textbox').fill('保留原因：相同工况下的方法值得验证');await row.getByRole('button',{name:'保存取舍',exact:true}).click();
 await expect(row.getByRole('button',{name:'保存取舍',exact:true})).toBeDisabled();
 await row.getByRole('combobox').selectOption('excluded');await row.getByRole('textbox').fill('排除原因：进一步核对发现工况不相容');await row.getByRole('button',{name:'保存取舍',exact:true}).click();
 await expect(row.getByRole('button',{name:'保存取舍',exact:true})).toBeDisabled();await page.reload();
 await expect(row.getByRole('combobox')).toHaveValue('excluded');await expect(row.getByRole('textbox')).toHaveValue('排除原因：进一步核对发现工况不相容');
 expect((await projectDetail(request,project.id)).project.revision).toBe(project.revision);
 await row.locator('.paper-title').click();const reader=page.getByRole('dialog',{name:'论文阅读',exact:true});const association=reader.getByRole('region',{name:'论文关联项目'}).getByRole('listitem').filter({hasText:project.title});
 await association.getByRole('button',{name:'查看项目',exact:false}).click();await expect(reader).not.toBeVisible();await expect(row).toBeVisible();
});

test('coverage repair opens the exact missing standard and impact inbox targets the invalid binding',async({page,request})=>{
 const project=await createProject(request,'coverage-ui');await page.goto(`/#page=projects&project_id=${project.id}`);
 await page.getByRole('navigation',{name:'项目章节'}).getByRole('button',{name:'核对证据',exact:true}).click();
 await page.locator('[data-criterion-id="risk"]').getByRole('button',{name:'补充此标准证据',exact:true}).click();
 const dialog=page.getByRole('dialog',{name:'从现有文库绑定证据'});await expect(dialog.getByLabel('对应评价标准',{exact:true})).toHaveValue('risk');
 await dialog.getByRole('button',{name:/等变图网络预测分子性质/}).click();await dialog.getByLabel('在本项目工况中的适用性',{exact:true}).fill('未复核隔离夹具仅检验风险标准的补证流程');await dialog.getByRole('button',{name:'绑定所选主张',exact:true}).click();await expect(dialog).not.toBeVisible();
 const detail=await projectDetail(request,project.id);expect(detail.evidence).toHaveLength(1);const evidence=detail.evidence[0];expect(evidence.criterion_id).toBe('risk');expect(detail.readiness.can_deliver).toBe(false);
 await page.goto('/#page=projects');const inbox=page.locator(`.project-impact-list [data-evidence-id="${evidence.id}"]`);await inbox.getByRole('button',{name:'进入项目核对',exact:true}).click();
 await expect(page).toHaveURL(new RegExp(`evidence_id=${evidence.id}`));await expect(page.locator(`#atlas-claim-${evidence.id}`)).toBeVisible();
});

test('candidate reasons and independent revisions survive status changes; paper associations remain read only',async({request})=>{
 const project=await createProject(request,'candidate-contract');const root=`/api/projects/${project.id}/candidates`;
 const added=await request.post(root,{headers,data:{paper_id:paperId,reason:'先纳入独立候选池'}});expect(added.ok()).toBeTruthy();const original=await added.json();
 const invalid=await request.put(`${root}/${original.id}`,{headers,data:{revision:original.revision,status:'excluded',reason:'短'}});expect(invalid.status()).toBe(422);
 const keptReason='保留理由为方法相近，需进一步核对工况';
 const kept=await request.put(`${root}/${original.id}`,{headers,data:{revision:original.revision,status:'kept',reason:keptReason}});expect(kept.ok()).toBeTruthy();const saved=await kept.json();expect(saved.reason).toBe(keptReason);expect(saved.revision).toBe(original.revision+1);
 const stale=await request.put(`${root}/${original.id}`,{headers,data:{revision:original.revision,status:'excluded',reason:'旧页面排除不得覆盖最新原因'}});expect(stale.status()).toBe(409);
 const excludedReason='排除理由为目标工况与本项目存在差异';const excluded=await request.put(`${root}/${original.id}`,{headers,data:{revision:saved.revision,status:'excluded',reason:excludedReason}});expect(excluded.ok()).toBeTruthy();
 const listed=await (await request.get(root)).json();expect(listed.items[0]).toMatchObject({status:'excluded',reason:excludedReason,revision:saved.revision+1});
 const duplicate=await request.post(root,{headers,data:{paper_id:paperId,reason:'重复添加不覆盖既有结论'}});expect((await duplicate.json()).id).toBe(original.id);
 const links=await (await request.get(`/api/projects/paper-links?paper_id=${paperId}`)).json();expect(links.items.find((p:any)=>p.project_id===project.id).candidate.reason).toBe(excludedReason);
 const detail=await projectDetail(request,project.id);expect(detail.project.revision).toBe(project.revision);expect(detail.evidence).toHaveLength(0);expect(detail.readiness.can_review).toBe(false);
});

test('unreviewed evidence appears in impact inbox with exact project, standard and binding identity',async({page,request})=>{
 const project=await createProject(request,'impact');const library=await(await request.get('/api/projects/library?q=Equivariant')).json();const source=library.items.find((p:any)=>p.paper_id===paperId);expect(source).toBeTruthy();
 const response=await request.post(`/api/projects/${project.id}/evidence`,{headers,data:{revision:project.revision,analysis_id:source.analysis_id,claim_index:source.claims[0].index,criterion_id:'risk',stance:'supports',context:'隔离夹具未复核，仅用于验证阻断与收件箱'}});expect(response.ok()).toBeTruthy();const evidence=await response.json();
 const impacts=await(await request.get('/api/projects/impacts')).json();const impact=impacts.items.find((item:any)=>item.evidence_id===evidence.id);expect(impact).toMatchObject({project_id:project.id,criterion_id:'risk',paper_id:paperId,bound_analysis_id:source.analysis_id,kind:'needs_verification'});expect(impact.issues.length).toBeGreaterThan(0);
 await page.goto(`/#page=projects&project_id=${project.id}&evidence_id=${evidence.id}`);await expect(page.locator(`#atlas-claim-${evidence.id}`)).toBeVisible();await page.reload();await expect(page.locator(`#atlas-claim-${evidence.id}`)).toBeVisible();
 const detail=await projectDetail(request,project.id);expect(detail.readiness.can_review).toBe(false);expect(detail.readiness.can_deliver).toBe(false);
});

test('candidate conflict preserves local reasons until the user explicitly adopts the latest revision',async({page,request})=>{
 const project=await createProject(request,'candidate-conflict');const endpoint=`/api/projects/${project.id}/candidates`;
 const created=await request.post(endpoint,{headers,data:{paper_id:paperId,reason:'冲突测试初始候选理由'}});expect(created.ok()).toBeTruthy();const candidate=await created.json();
 await page.goto(`/#page=projects&project_id=${project.id}&candidate_id=${candidate.id}`);
 const row=page.locator(`[data-candidate-id="${candidate.id}"]`),reason=row.getByRole('textbox'),save=row.getByRole('button',{name:'保存取舍',exact:true});
 const localReason='本机正在编辑的保留理由，不能被远端覆盖',remoteReason='另一位审阅者已排除此候选，工况尚不匹配';
 await row.getByRole('combobox').selectOption('kept');await reason.fill(localReason);
 const remote=await request.put(`${endpoint}/${candidate.id}`,{headers,data:{revision:candidate.revision,status:'excluded',reason:remoteReason}});expect(remote.ok()).toBeTruthy();const remoteCandidate=await remote.json();
 const conflict=page.waitForResponse(response=>response.request().method()==='PUT'&&new URL(response.url()).pathname===`${endpoint}/${candidate.id}`&&response.status()===409);
 await save.click();await conflict;
 await expect(reason).toHaveValue(localReason);await expect(row.getByRole('combobox')).toHaveValue('kept');await expect(row.getByRole('alert')).toContainText('输入已保留');
 await expect(row.locator('.project-candidate-conflict')).toContainText(remoteReason);await expect(row.locator('.project-candidate-conflict')).toContainText(`当前修订 ${remoteCandidate.revision}`);await expect(save).toBeDisabled();
 await row.getByRole('button',{name:'重载候选（保留输入）',exact:true}).click();await expect(reason).toHaveValue(localReason);await expect(save).toBeDisabled();
 await row.getByRole('button',{name:'按最新修订继续编辑',exact:true}).click();await expect(reason).toHaveValue(localReason);await expect(save).toBeEnabled();await save.click();await expect(save).toBeDisabled();
 await expect.poll(async()=>(await(await request.get(endpoint)).json()).items[0]).toMatchObject({reason:localReason,status:'kept',revision:remoteCandidate.revision+1});
 expect((await projectDetail(request,project.id)).project.revision).toBe(project.revision);
});

test('mobile reduced-motion discovery stays read only and Escape closes only the nested capture dialog',async({page,request},testInfo)=>{
 const project=await createProject(request,'mobile-isolated-fixture');
 const created=await request.post(`/api/projects/${project.id}/candidates`,{headers,data:{paper_id:paperId,reason:'隔离移动端布局与键盘核查夹具'}});expect(created.ok()).toBeTruthy();const candidate=await created.json();
 await page.setViewportSize({width:390,height:844});await page.emulateMedia({reducedMotion:'reduce'});
 // Setup uses request above; browsing below must not write or start analysis.
 const writes:string[]=[],modelCalls:string[]=[];
 page.on('request',req=>{const path=new URL(req.url()).pathname;if(path.startsWith('/api/')&&!['GET','HEAD'].includes(req.method()))writes.push(`${req.method()} ${path}`);if(/\/api\/(analyze|exploration|chat|model)/.test(path)&&!['GET','HEAD'].includes(req.method()))modelCalls.push(path)});
 const noOverflow=async()=>expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await page.goto(`/#page=projects&project_id=${project.id}&candidate_id=${candidate.id}`);
 await expect(page.locator(`[data-candidate-id="${candidate.id}"]`)).toBeVisible();await expect(page.getByRole('region',{name:'评价标准证据覆盖'})).toBeVisible();await noOverflow();
 await page.screenshot({path:testInfo.outputPath('isolated-fixture-candidates-coverage-mobile.png'),fullPage:true});
 await page.goto('/#page=papers&days=0');const row=page.locator(`[data-paper-id="${paperId}"]`);await row.getByRole('button',{name:'摘要与分析概要',exact:true}).click();await row.getByRole('button',{name:'加入项目线索',exact:true}).click();
 let capture=page.getByRole('dialog',{name:'加入项目线索',exact:true});await expect(capture).toBeVisible();await expect(capture.getByLabel('目标项目',{exact:true})).toBeVisible();await noOverflow();await page.keyboard.press('Escape');await expect(capture).not.toBeVisible();await expect(row.getByRole('region',{name:/的摘要与分析概要/})).toBeVisible();
 await row.locator('.paper-title').click();const reader=page.getByRole('dialog',{name:'论文阅读',exact:true});await expect(reader).toBeVisible();await reader.getByRole('button',{name:'加入项目线索',exact:true}).click();capture=page.getByRole('dialog',{name:'加入项目线索',exact:true});await expect(capture).toBeVisible();await noOverflow();
 await page.screenshot({path:testInfo.outputPath('isolated-fixture-nested-capture-mobile.png')});await page.keyboard.press('Escape');await expect(capture).not.toBeVisible();await expect(reader).toBeVisible();await noOverflow();
 expect(writes).toEqual([]);expect(modelCalls).toEqual([]);expect((await projectDetail(request,project.id)).project.revision).toBe(project.revision);
});

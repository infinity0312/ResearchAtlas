import {test,expect} from '@playwright/test';

test('project workspace displays an AgentArts draft and requires a separate adoption action',async({page,request,baseURL})=>{
 expect(new URL(baseURL!).port).toBe('8770');
 const headers={'X-Atlas-Client':'1'};
 const created=await request.post('/api/projects',{headers,data:{
  title:'AgentArts 证据联调夹具',scenario:'material_substitution',
  question:'候选材料是否满足导热要求？',constraints:'测试数据',
  criteria:[{id:'thermal',label:'导热表现'}],
 }});
 expect(created.ok()).toBeTruthy();
 const project=await created.json();
 const path='/api/projects/'+project.id+'/agentarts';
 let review:object|null=null;
 let starts=0, binds=0;
 const draft={
  id:'mock-review',state:'ready',query:'thermal',project_revision:1,expected_revision:1,stale:false,
  execution_id:'fixture-trace',error:'',bindings:{},
  sources:[{evidence_id:'e1',paper_id:'2609.00000',paper_version:1,title:'隔离证据夹具',pdf_page:2,quote:'A tested excerpt from the second page.'}],
  assessments:[{criterion_id:'thermal',label:'导热表现',status:'supported',next_step:'复核同工况',
    findings:[{evidence_id:'e1',stance:'supports',reason:'具有评审所需的相同工况'}]}],
 };
 await page.route('**'+path,async route=>{
  if(route.request().method()==='GET')return route.fulfill({json:{enabled:true,configured:true,review}});
  starts++;
  expect(route.request().postDataJSON()).toEqual({revision:1,query:'thermal'});
  review=draft;
  await route.fulfill({json:review});
 });
 await page.route('**'+path+'/mock-review/bind',async route=>{
  binds++;
  expect(route.request().postDataJSON()).toEqual({revision:1,criterion_id:'thermal',evidence_id:'e1'});
  review={...draft,bindings:{'thermal:e1':'attached'}};
  await route.fulfill({json:review});
 });
 await page.setViewportSize({width:390,height:844});
 await page.goto('/#page=projects&project_id='+project.id);
 await page.getByRole('button',{name:'核对证据',exact:true}).click();
 const panel=page.getByRole('region',{name:'AgentArts 证据评审'});
 await panel.getByRole('searchbox',{name:'检索关键词'}).fill('thermal');
 await panel.getByRole('button',{name:'运行 AgentArts 评审'}).click();
 await expect(panel).toContainText('fixture-trace');
 expect(binds).toBe(0);
 await panel.locator('summary').click();
 await expect(panel.getByRole('link',{name:'查看该版本原页'})).toHaveAttribute('href','/api/paper/pdf?id=2609.00000&version=1#page=2');
 await panel.getByRole('button',{name:'采纳此证据'}).click();
 await expect(panel.getByText('已采纳',{exact:true})).toBeVisible();
 expect(starts).toBe(1);
 expect(binds).toBe(1);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

import {test,expect} from '@playwright/test';
test('rapid terminal navigation keeps final route usable without rejected transitions',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>{localStorage.setItem('atlas.appearance.v1',JSON.stringify({edition:'prism',motion:'system',effects:'off'}));sessionStorage.setItem('atlas.terminal.entered','1')});
 await page.goto('/#page=overview');await expect(page.locator('.page-heading h1')).toBeVisible();
 await page.evaluate(()=>{const nav=document.querySelector('nav')||document.querySelector('.sidebar');for(const name of ['发现论文','领域趋势','后台任务']){const button=Array.from(nav!.querySelectorAll('button')).find(b=>b.textContent?.trim()===name);button?.click()}});
 await page.getByRole('button',{name:'工作台设置',exact:true}).count().then(async n=>{if(n)await page.getByRole('button',{name:'工作台设置',exact:true}).click();else await page.getByRole('button',{name:'设置与连接',exact:true}).click()});
 await expect(page.locator('.appearance-settings')).toBeVisible();await expect.poll(()=>page.evaluate(()=>document.documentElement.hasAttribute('data-route-transition'))).toBe(false);expect(errors).toEqual([]);
});

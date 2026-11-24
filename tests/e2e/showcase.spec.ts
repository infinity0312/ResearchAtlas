import {readFile} from 'node:fs/promises';
import {expect, test} from '@playwright/test';

test('the product page leads with AI reading and keeps the case separate', async ({page, request}) => {
  await page.setViewportSize({width: 390, height: 844});
  await page.goto('/showcase/');
  const gallery = page.locator('figure.showcase-product-image');
  await expect(gallery).toHaveCount(9);
  await expect(gallery.first().locator('img')).toHaveAttribute('src', './media/paper-evidence.png');
  await page.getByRole('link', {name: '看 AI 研读'}).click();
  await expect(page).toHaveURL(/#reading$/);
  const reading = page.getByRole('region', {name: '一篇论文怎样读深'});
  await expect(reading.getByRole('figure')).toHaveCount(3);
  await expect(reading.getByRole('link', {name: '论文原页'})).toHaveAttribute('href', 'https://arxiv.org/pdf/2603.22733v1#page=9');
  for (const figure of await gallery.all()) {
    await figure.scrollIntoViewIfNeeded();
    await expect.poll(() => figure.locator('img').evaluate(image => (image as HTMLImageElement).naturalWidth))
      .toBeGreaterThan(900);
    const link = await figure.getByRole('link').getAttribute('href');
    const original = await request.get(new URL(link!, page.url()).href);
    expect(original.headers()['content-type']).toMatch(/^image\/png/);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  await expect(page.getByRole('heading', {name: '走完一项研发决策'})).toHaveCount(0);
  await page.getByRole('link', {name: '体验材料评审'}).click();
  await expect(page).toHaveURL(/\?view=demo#demo$/);
  await expect(page.getByRole('heading', {name: '走完一项研发决策'})).toBeVisible();
  await page.getByRole('link', {name: '返回产品展示'}).click();
  await expect(gallery).toHaveCount(9);
});

test('from an external source to a frozen decision and a targeted version review', async ({page, request}) => {
  const errors: string[] = [];
  const apiRequests: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/**', route => {
    apiRequests.push(route.request().url());
    return route.abort();
  });
  await page.goto('/showcase/');
  await expect(page.getByRole('heading', {level: 1})).toHaveText('用 AI 读懂论文，回到原文核对');
  await page.getByRole('link', {name: '体验材料评审'}).click();
  await page.getByRole('button', {name: '检索样例语料'}).click();
  const results = page.getByRole('region', {name: '检索结果'});
  await expect(results.locator('.case-rank li').first()).toContainText('直接匹配');
  await results.getByText('展开趋势线索', {exact: false}).click();
  await expect(results.getByText('历史窗口截至 2026-03-24', {exact: false})).toBeVisible();
  await results.getByRole('button', {name: '收录并关联 v1'}).click();
  await expect(results.getByRole('status')).toContainText('TIM-L01');
  await expect(results.getByRole('button', {name: '收录并关联 v1'})).toHaveCount(0);
  await results.getByRole('button', {name: '进入证据评审'}).click();
  await expect(page.getByRole('heading', {name: '核对原页'})).toBeFocused();
  await expect(page.getByRole('button', {name: '进入验证计划'})).toBeDisabled();

  const method = page.locator('details.agentarts-finding').filter({hasText: 'Chen'});
  await method.locator('summary').click();
  await expect(method.getByRole('link', {name: '查看该版本原页'}))
    .toHaveAttribute('href', 'https://arxiv.org/pdf/2603.22733v1#page=1');
  await method.getByRole('button', {name: '采纳此证据'}).click();
  const bench = page.locator('details.agentarts-finding').filter({has: page.locator('summary').filter({hasText: '台架记录'})});
  await bench.locator('summary').click();
  await expect(bench.getByRole('link', {name: '查看该版本原页'})).toHaveAttribute('href', './sources/panel-b.pdf#page=1');
  const pdf = await request.get('/showcase/sources/panel-b.pdf');
  expect(pdf.ok()).toBeTruthy();
  expect(pdf.headers()['content-type']).toMatch(/^application\/pdf/);
  expect((await pdf.body()).toString()).toContain('Fictional test B did not meet');
  await bench.getByRole('button', {name: '采纳此证据'}).click();

  await page.getByRole('button', {name: '进入验证计划'}).click();
  await page.getByRole('button', {name: '记录决定与验证计划'}).click();
  await expect(page.getByText('暂缓替换，安排同工况复测', {exact: true})).toBeVisible();
  await page.getByRole('button', {name: '进入交付'}).click();
  await expect(page.getByRole('button', {name: '冻结评审交付'})).toHaveCount(0);
  await page.getByRole('button', {name: '记录人工复核'}).click();
  await page.getByRole('button', {name: '冻结评审交付'}).click();
  await expect(page.getByText(/RA-TIM-R04 · 项目修订 4/)).toBeVisible();
  const captureArchive = async () => {
    const [download] = await Promise.all([
      page.waitForEvent('download'), page.getByRole('button', {name: '下载归档 Markdown'}).click(),
    ]);
    return readFile((await download.path())!, 'utf8');
  };
  const archive = await captureArchive();
  expect(archive).toContain('TIM-L01');
  expect(archive).toContain('2603.22733v1#page=1');
  expect(archive).toContain('样例采纳 · e2');
  expect(archive).toContain('待录入结果');
  expect(archive).toContain('演示评审人');

  await page.getByRole('button', {name: '检查来源更新'}).click();
  await page.getByRole('button', {name: '回放 v2 发布事件'}).click();
  const versions = page.getByRole('group', {name: '论文版本对照'});
  await expect(versions.getByRole('link', {name: /新版本 v2/})).toHaveAttribute('href', 'https://arxiv.org/pdf/2603.22733v2#page=1');
  await expect(page.getByRole('heading', {name: '受影响的评审标准 · 装配工况可比性'})).toBeVisible();
  await page.getByRole('button', {name: '加入复核清单'}).click();
  await expect(page.getByText('已加入复核清单 · 装配工况可比性')).toBeVisible();
  await page.getByRole('button', {name: '归档交付'}).click();
  expect(await captureArchive()).toBe(archive);
  expect(errors).toEqual([]);
  expect(apiRequests).toEqual([]);
});

test('compact flow handles no match, keyboard focus and a complete reset', async ({page}) => {
  await page.emulateMedia({reducedMotion: 'reduce'});
  await page.setViewportSize({width: 390, height: 844});
  await page.goto('/showcase/');
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).scrollBehavior)).toBe('auto');
  await page.getByRole('link', {name: '体验材料评审'}).click();
  await page.getByRole('radio', {name: '候选 B 的长期热老化结果'}).check();
  await page.getByRole('button', {name: '检索样例语料'}).press('Enter');
  await expect(page.getByText('未找到候选 B 的长期热老化证据')).toBeVisible();
  await expect(page.getByRole('button', {name: '核对原页'})).toBeDisabled();
  await page.getByRole('button', {name: '调整检索'}).click();
  await expect(page.getByRole('radio', {name: '装配压力与界面热阻'})).toBeFocused();
  await page.getByRole('button', {name: '检索样例语料'}).click();
  await page.getByRole('button', {name: '收录并关联 v1'}).click();
  await page.getByRole('button', {name: '重置体验'}).click();
  await expect(page.getByRole('region', {name: '检索结果'})).toHaveCount(0);
  await page.getByRole('button', {name: '检索样例语料'}).click();
  await page.getByRole('button', {name: '收录并关联 v1'}).click();
  await page.getByRole('button', {name: '进入证据评审'}).click();
  await expect(page.getByRole('heading', {name: '核对原页'})).toBeFocused();
  await page.locator('summary').filter({hasText: 'Chen'}).press('Enter');
  await expect(page.getByRole('link', {name: '查看该版本原页'})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  await page.getByRole('button', {name: '重置体验'}).click();
  await expect(page.getByRole('button', {name: '核对原页'})).toBeDisabled();
});

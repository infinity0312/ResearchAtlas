import {readFile} from 'node:fs/promises';
import {expect, test} from '@playwright/test';

test('the standalone showcase replays a decision and exports the adopted source', async ({page, request}) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/**', route => route.abort());
  await page.goto('/showcase/');
  await expect(page.getByRole('heading', {level: 1})).toHaveText('把研究证据带进研发决策');
  await page.getByRole('link', {name: '体验材料评审'}).click();
  await page.getByRole('button', {name: '检索样例语料'}).click();
  await expect(page.getByRole('heading', {name: '核对原页'})).toBeFocused();
  await expect(page.getByText('有反对依据', {exact: true}).last()).toBeVisible();
  await expect(page.getByText('证据不足', {exact: true}).last()).toBeVisible();
  await page.locator('summary').filter({hasText: 'B 组'}).click();
  const source = page.getByRole('link', {name: '查看该版本原页'});
  await expect(source).toHaveAttribute('href', './sources/panel-b.pdf#page=1');
  const pdf = await request.get('/showcase/sources/panel-b.pdf');
  expect(pdf.ok()).toBeTruthy();
  expect(pdf.headers()['content-type']).toMatch(/^application\/pdf/);
  expect((await pdf.body()).toString()).toContain('Fictional test B did not meet');
  await page.getByRole('button', {name: '采纳此证据'}).click();
  await expect(page.getByText('本轮已采纳 1 条依据')).toBeVisible();
  await page.getByRole('button', {name: '查看交付草稿'}).click();
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', {name: '下载 Markdown 草稿'}).click(),
  ]);
  const markdown = await readFile((await download.path())!, 'utf8');
  expect(markdown).toContain('样例回放');
  expect(markdown).toContain('panel-b.pdf#page=1');
  expect(markdown).toContain('样例采纳 · e2');
  expect(markdown).toContain('电绝缘验证');
  expect(errors).toEqual([]);
});

test('the compact showcase supports empty retrieval, recovery and reduced motion', async ({page}) => {
  await page.emulateMedia({reducedMotion: 'reduce'});
  await page.setViewportSize({width: 390, height: 844});
  await page.goto('/showcase/');
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).scrollBehavior)).toBe('auto');
  await page.getByRole('link', {name: '体验材料评审'}).click();
  await page.getByRole('radio', {name: '长期热老化试验'}).check();
  await page.getByRole('button', {name: '检索样例语料'}).press('Enter');
  await expect(page.getByText('未找到可核对的长期热老化证据')).toBeVisible();
  await expect(page.getByRole('button', {name: '交付草稿'})).toBeDisabled();
  await page.getByRole('button', {name: '调整检索'}).click();
  await page.getByRole('radio', {name: '基准工况下的导热试验'}).check();
  await page.getByRole('button', {name: '检索样例语料'}).click();
  await page.locator('summary').filter({hasText: 'A 组'}).press('Enter');
  await expect(page.getByRole('link', {name: '查看该版本原页'})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  await page.getByRole('button', {name: '重置体验'}).click();
  await expect(page.getByRole('button', {name: '核对原页'})).toBeDisabled();
});

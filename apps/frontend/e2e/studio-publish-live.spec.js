import path from 'node:path';
import fs from 'node:fs';
import { expect, test } from '@playwright/test';

test('real API: source library survives reload and requires a fresh analysis', async ({ page }) => {
  test.skip(!process.env.REPORTER_STUDIO_TEST_API, 'Requires isolated temporary-data API');
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const response = await route.fetch({
      url: `${process.env.REPORTER_STUDIO_TEST_API}${url.pathname}${url.search}`,
    });
    await route.fulfill({ response });
  });
  const source = await page.request.get(
    `${process.env.REPORTER_STUDIO_TEST_API}/__test/unprepared.docx`,
  );
  const filename = `library-review-${Date.now()}.docx`;
  const stored = await page.request.post(
    `${process.env.REPORTER_STUDIO_TEST_API}/api/template-packs/analyze-template`,
    {
      data: {
        filename,
        contentBase64: (await source.body()).toString('base64'),
        reportType: 'full',
      },
    },
  );
  expect(stored.ok()).toBe(true);
  await page.goto('/?view=template-studio');
  await page.waitForLoadState('networkidle');
  await page.reload();
  await page.getByRole('button', { name: 'Quản lý', exact: true }).click();
  await page.getByRole('button', { name: 'Template mới', exact: true }).click();
  await page.getByRole('button', { name: 'Thư viện nguồn', exact: true }).click();
  await page.getByRole('textbox', { name: 'Tìm template đã lưu' }).fill('library-review');
  await page.getByRole('button', { name: 'Tìm', exact: true }).click();
  const choice = page.locator('.ts-source-library-item').first();
  await expect(choice).toBeVisible();
  await page.screenshot({ path: 'test-results/source-library-dark.png', fullPage: true });
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'light'));
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.screenshot({ path: 'test-results/source-library-light.png', fullPage: true });
  await page.setViewportSize({ width: 760, height: 850 });
  await page.screenshot({ path: 'test-results/source-library-narrow.png', fullPage: true });
  await choice.click();
  await expect(page.getByRole('button', { name: 'Tạo workspace', exact: true })).toBeDisabled();
  await page.getByLabel(/^Profile ID/).fill('library-reuse');
  await page.getByRole('button', { name: 'Phân tích', exact: true }).click();
  await expect(page.getByText('Đã phân tích an toàn')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Tạo workspace', exact: true })).toBeEnabled();
});

test('real API: map → review → validate → publish → production preview/generate', async ({
  page,
}) => {
  test.skip(!process.env.REPORTER_STUDIO_TEST_API, 'Requires isolated temporary-data API');
  test.setTimeout(120000);
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const response = await route.fetch({
      url: `${process.env.REPORTER_STUDIO_TEST_API}${url.pathname}${url.search}`,
      timeout: 60000,
    });
    await route.fulfill({ response });
  });
  await page.goto('/?view=template-studio');
  await page.getByRole('button', { name: 'Quản lý', exact: true }).click();
  await page.getByRole('button', { name: 'Template mới', exact: true }).click();
  const fixtureDir = path.resolve('../../tests/fixtures/template_studio/synthetic_templates');
  const fixture = JSON.parse(fs.readFileSync(path.join(fixtureDir, 'manifest.json'), 'utf8'))
    .fixtures.full;
  const profileId = `live-fixture-${Date.now()}`;
  await page
    .locator('input[type="file"][accept=".docx"]')
    .setInputFiles(path.join(fixtureDir, fixture.file));
  await page.getByLabel(/^Profile ID/).fill(profileId);
  await page.getByRole('button', { name: 'Phân tích', exact: true }).click();
  await page.getByRole('button', { name: 'Tạo workspace', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Ánh xạ template' })).toBeVisible();
  for (const [semantic, anchor] of Object.entries(fixture.anchors)) {
    await page
      .locator('.ts-row-button')
      .filter({
        has: page.locator('small', { hasText: new RegExp(`^${semantic.replaceAll('.', '\\.')}$`) }),
      })
      .click();
    await page.locator('#ts-anchor').selectOption(`${anchor.kind}:${anchor.value}`);
    const fields = page.getByRole('textbox', { name: /^Cột Word cho/ });
    for (let index = 0; index < (await fields.count()); index++)
      await fields.nth(index).fill(`column:${index + 1}`);
    const saved = page.waitForResponse(
      (res) => res.url().includes('/mappings/') && res.request().method() === 'PUT',
    );
    await page.getByRole('button', { name: 'Duyệt ánh xạ', exact: true }).click();
    expect((await saved).status()).toBe(200);
  }
  await page.getByRole('button', { name: 'Rà soát template', exact: true }).click();
  await page.getByRole('button', { name: 'Tạo báo cáo thử', exact: true }).click();
  await page
    .getByRole('dialog', { name: 'Kiểm thử Template Pack' })
    .locator('input[type="file"]')
    .setInputFiles({
      name: 'tracking-test.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(
        'type,hostname,ip,os,result\nserver,LIVE-SRV-01,10.1.1.1,Linux,Malware detected\nclient,LIVE-PC-01,10.1.1.2,Windows,Clean\n',
      ),
    });
  await page.getByRole('button', { name: 'Tạo baseline', exact: true }).click();
  await page.getByRole('button', { name: 'Tải DOCX để duyệt', exact: true }).click();
  await page.getByLabel('Người duyệt', { exact: true }).fill('Automated synthetic fixture review');
  await page.getByRole('button', { name: 'Duyệt baseline', exact: true }).click();
  await page.getByRole('button', { name: 'Chạy lượt xác minh', exact: true }).click();
  await page.getByRole('button', { name: 'Tải DOCX để duyệt', exact: true }).click();
  await page.getByRole('button', { name: 'Phát hành vào Catalog', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Template Pack đã được phát hành' }),
  ).toBeVisible();
  // The production API must expose the published pack for explicit selection.
  const templates = await page.request.get(`${process.env.REPORTER_STUDIO_TEST_API}/api/templates`);
  const pack = (await templates.json()).templates.find((item) =>
    item.path?.startsWith(`rptpack:${profileId}:`),
  );
  expect(pack).toBeTruthy();
  expect(pack.isDefault).toBe(false);
  await page.getByRole('button', { name: 'Đóng kiểm thử', exact: true }).click();
  await page.getByRole('link', { name: 'Quay lại Reporter Pro' }).click();
  await page.getByRole('button', { name: /Tạo báo cáo/i }).click();
  const chooserPromise = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: 'Tiếp tục', exact: true }).click();
  await (
    await chooserPromise
  ).setFiles({
    name: 'live.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(
      'type,hostname,ip,os,result\nserver,LIVE-SRV-01,10.1.1.1,Linux,Malware detected\nclient,LIVE-PC-01,10.1.1.2,Windows,Clean\n',
    ),
  });
  await expect(page.getByText('LIVE-SRV-01', { exact: true }).first()).toBeVisible();
  await page.locator('.sidebar__nav-item').filter({ hasText: 'Cấu hình' }).click();
  await page.getByLabel('Template báo cáo').selectOption(pack.path);
  await page.locator('.sidebar__nav-item').filter({ hasText: 'Xuất báo cáo' }).click();
  await page.getByRole('button', { name: /Xem trước báo cáo/i }).click();
  await expect(page.locator('.docx-modal')).toBeVisible();
  const downloaded = page.waitForResponse(
    (res) => /\/api\/report-jobs\/[^/]+\/download$/.test(res.url()) && res.ok(),
  );
  await page
    .locator('.docx-modal__footer')
    .getByRole('button', { name: /Generate từ Preview này/i })
    .click();
  expect((await downloaded).headers()['content-type']).toContain('wordprocessingml');
  await expect(page.getByRole('button', { name: /Tải lại/i })).toBeVisible();
});

test('real API: normalize an unprepared Word document without changing its source', async ({
  page,
}) => {
  test.skip(!process.env.REPORTER_STUDIO_TEST_API, 'Requires isolated temporary-data API');
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const response = await route.fetch({
      url: `${process.env.REPORTER_STUDIO_TEST_API}${url.pathname}${url.search}`,
    });
    await route.fulfill({ response });
  });
  const source = await page.request.get(
    `${process.env.REPORTER_STUDIO_TEST_API}/__test/unprepared.docx`,
  );
  expect(source.status()).toBe(200);
  await page.goto('/?view=template-studio');
  await page.getByRole('button', { name: 'Quản lý', exact: true }).click();
  await page.getByRole('button', { name: 'Template mới', exact: true }).click();
  await page.locator('input[type="file"][accept=".docx"]').setInputFiles({
    name: 'unprepared.docx',
    mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    buffer: await source.body(),
  });
  await page.getByRole('button', { name: 'Phân tích', exact: true }).click();
  await page.getByRole('button', { name: 'Tạo workspace', exact: true }).click();
  await page.getByRole('button', { name: 'Chuẩn hóa cấu trúc', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Chuẩn hóa cấu trúc' });
  const positions = dialog.getByRole('combobox', { name: /^Vị trí / });
  await expect(positions.first()).toBeVisible();
  for (let index = 0; index < (await positions.count()); index++) {
    await positions.nth(index).selectOption(String(index + 1));
    await dialog
      .getByRole('combobox', { name: /^Chế độ / })
      .nth(index)
      .selectOption('replace');
  }
  await page.screenshot({ path: 'test-results/normalization-light.png', fullPage: true });
  const created = page.waitForResponse(
    (res) => res.url().endsWith('/normalize') && res.request().method() === 'POST',
  );
  await dialog.getByRole('button', { name: 'Tạo bản chuẩn hóa' }).click();
  const result = await created;
  expect(result.status()).toBe(201);
  expect((await result.json()).coveragePercent).toBe(0);
  await expect(dialog).not.toBeVisible();
  await expect(page.getByRole('heading', { name: 'Ánh xạ template' })).toBeVisible();
});

import path from 'node:path';
import { expect, test } from '@playwright/test';

test('real backend: import survives Studio navigation, analysis and browser history', async ({
  page,
}) => {
  test.skip(!process.env.REPORTER_LIVE_API, 'Requires an explicitly supplied local backend');
  const calls = [];
  await page.route('**/api/**', async (route) => {
    const source = new URL(route.request().url());
    calls.push(source.pathname);
    const response = await route.fetch({
      url: `${process.env.REPORTER_LIVE_API}${source.pathname}${source.search}`,
    });
    await route.fulfill({ response });
  });
  await page.goto('/');
  await page.getByRole('button', { name: /Tạo báo cáo/i }).click();
  const chooserPromise = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: 'Tiếp tục' }).click();
  const chooser = await chooserPromise;
  await chooser.setFiles({
    name: 'navigation-test.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('type,hostname,ip,os,result\nserver,NAV-SERVER-01,10.0.0.10,Linux,Clean\n'),
  });
  await expect(page.getByText('NAV-SERVER-01', { exact: true }).first()).toBeVisible();
  // Development StrictMode probes the initial mount with an open/close/open cycle.
  const closesBeforeNavigation = calls.filter((p) => p === '/api/runtime/browser/close').length;
  await page.getByRole('link', { name: 'Template Studio', exact: true }).click();
  await page.getByRole('button', { name: 'Quản lý', exact: true }).click();
  await page.getByRole('button', { name: 'Template mới', exact: true }).click();
  await page
    .locator('input[type="file"][accept=".docx"]')
    .setInputFiles(
      path.resolve(
        '../../tests/fixtures/template_studio/synthetic_templates/cross_platform_assessment_full.docx',
      ),
    );
  await page.getByRole('button', { name: 'Phân tích', exact: true }).click();
  await expect(page.getByText('Đã phân tích an toàn')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Tạo workspace', exact: true })).toBeEnabled();
  await expect
    .poll(() => calls.filter((p) => p === '/api/runtime/browser/heartbeat').length, {
      timeout: 10000,
    })
    .toBeGreaterThanOrEqual(3);
  await page.getByRole('button', { name: 'Hủy', exact: true }).click();
  await page.getByRole('button', { name: 'Đóng quản lý workspace' }).click();
  await page.getByRole('link', { name: 'Quay lại Reporter Pro' }).click();
  await expect(page.getByText('NAV-SERVER-01', { exact: true }).first()).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('link', { name: 'Quay lại Reporter Pro' })).toBeVisible();
  await page.goForward();
  await expect(page.getByText('NAV-SERVER-01', { exact: true }).first()).toBeVisible();
  expect(calls.filter((p) => p === '/api/runtime/browser/close')).toHaveLength(
    closesBeforeNavigation,
  );
});

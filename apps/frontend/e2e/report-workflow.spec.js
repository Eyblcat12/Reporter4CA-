import path from 'node:path';
import { expect, test } from '@playwright/test';

const sampleRows = [
  { type: 'server', hostname: 'srv-e2e-01', ip: '10.0.0.10', os: 'Linux', result: 'Clean', notes: '' },
  { type: 'client', hostname: 'ws-e2e-01', ip: '10.0.0.20', os: 'Windows', result: 'Reviewed', notes: 'Acme Relay observed' },
];

test('import sample → configure → preview → generate', async ({ page }) => {
  const docxPath = path.resolve('../backend/templates/report_template.docx');
  let previewRequested = false;
  let generateRequested = false;
  let ruleEvaluated = false;
  let ruleSaved = false;
  let customRules = [];

  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const pathname = url.pathname;
    if (pathname === '/api/sample') {
      return route.fulfill({ json: {
        rows: sampleRows, payload: {}, counts: { servers: 1, clients: 1, total: 2 }, previewText: 'sample',
      } });
    }
    if (pathname === '/api/validate-rows') {
      return route.fulfill({ json: {
        valid: true, issues: [], summary: {
          totalRows: 2, validRows: 2, errorRows: 0, warningRows: 0,
          errors: 0, warnings: 0, servers: 1, clients: 1,
          duplicateHostnames: 0, invalidIps: 0, missingOs: 0, missingResult: 0,
        },
      } });
    }
    if (pathname === '/api/preview-docx') {
      previewRequested = true;
      return route.fulfill({ path: docxPath, contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
    }
    if (pathname === '/api/rules/evaluate' && route.request().method() === 'POST') {
      const request = route.request().postDataJSON();
      ruleEvaluated = request.rule.name === 'Acme Relay review'
        && request.rule.conditions.containsAny.includes('Acme Relay');
      return route.fulfill({ json: {
        matchedRows: 1, totalRows: 2,
        matches: [{
          row: 1, hostname: 'ws-e2e-01', type: 'client',
          evidence: [{ field: 'notes', value: 'Acme Relay observed', matched: 'acme relay' }],
        }],
      } });
    }
    if (pathname === '/api/rules' && route.request().method() === 'POST') {
      const request = route.request().postDataJSON();
      ruleSaved = request.name === 'Acme Relay review';
      const saved = { ...request, id: 'CUSTOM_E2E', source: 'custom', editable: true };
      customRules = [saved];
      return route.fulfill({ status: 201, json: saved });
    }
    if (pathname === '/api/rules' && route.request().method() === 'GET') {
      return route.fulfill({ json: { schemaVersion: '1.0', rules: customRules } });
    }
    if (pathname === '/api/report-jobs' && route.request().method() === 'POST') {
      generateRequested = true;
      return route.fulfill({ status: 202, json: {
        job: { id: 'e2e-job', status: 'queued', phase: 'queued', progress: 0 },
        deduplicated: false,
      } });
    }
    if (pathname === '/api/report-jobs/e2e-job') {
      return route.fulfill({ json: { job: {
        id: 'e2e-job', status: 'completed', phase: 'completed', progress: 100,
        filename: 'e2e-report.docx', reportId: 'e2e-1', message: 'Completed',
      } } });
    }
    if (pathname === '/api/report-jobs/e2e-job/download') {
      return route.fulfill({
        path: docxPath,
        contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers: { 'Content-Disposition': 'attachment; filename="e2e-report.docx"' },
      });
    }
    if (pathname === '/api/templates') return route.fulfill({ json: { templates: [] } });
    if (pathname === '/api/presets') return route.fulfill({ json: { presets: [] } });
    if (pathname === '/api/reports/history') return route.fulfill({ json: { reports: [] } });
    if (pathname === '/api/dashboard/summary') {
      return route.fulfill({ json: { days: Number(url.searchParams.get('days') || 90), metrics: {}, series: [], recent: [] } });
    }
    return route.fulfill({ status: 404, json: { detail: 'Not mocked' } });
  });

  await page.goto('/');
  await page.getByRole('button', { name: /Tạo báo cáo/i }).click();
  await page.getByRole('button', { name: 'Mẫu' }).click();
  await page.getByRole('button', { name: 'Tiếp tục' }).click();
  await expect(page.getByText('srv-e2e-01')).toBeVisible();
  await expect(page.getByText('Chất lượng dữ liệu')).toBeVisible();

  await page.locator('.sidebar__nav-item').filter({ hasText: 'Cấu hình' }).click();
  const titleInput = page.locator('input[type="text"]').first();
  await titleInput.fill('E2E Assessment');

  await page.getByRole('button', { name: /Thêm rule/i }).click();
  await page.getByLabel(/Tên rule/i).fill('Acme Relay review');
  await page.getByLabel(/Từ khóa cần khớp/i).fill('Acme Relay');
  await page.getByRole('button', { name: /Thử trên 2 dòng/i }).click();
  await expect(page.getByText(/Khớp 1\/2 dòng/i)).toBeVisible();
  expect(ruleEvaluated).toBe(true);
  await page.getByRole('button', { name: /Lưu rule/i }).click();
  await expect(page.getByText('Acme Relay review')).toBeVisible();
  expect(ruleSaved).toBe(true);

  await page.locator('.sidebar__nav-item').filter({ hasText: 'Xuất báo cáo' }).click();
  await page.getByRole('button', { name: /Xem trước báo cáo/i }).click();
  await expect(page.locator('.docx-modal')).toBeVisible();
  expect(previewRequested).toBe(true);

  const downloadPromise = page.waitForEvent('download');
  await page.locator('.docx-modal__footer').getByRole('button', { name: /Tạo báo cáo DOCX/i }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('e2e-report.docx');
  expect(generateRequested).toBe(true);
});

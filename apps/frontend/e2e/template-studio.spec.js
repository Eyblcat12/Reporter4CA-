import { expect, test } from '@playwright/test';

const workspace = {
  workspaceId: 'workspace-e2e',
  profileId: 'customer-full',
  displayName: 'Customer Full',
  version: '0.1.0',
  reportType: 'full',
  status: 'mapping_incomplete',
  archived: false,
  revision: 1,
  coveragePercent: 0,
  updatedAt: '2026-09-02T12:00:00Z',
  templateSha256: 'a'.repeat(64),
  analysis: {
    facts: {
      contentControls: Array.from({ length: 10 }, (_, index) => ({
        value: index === 9 ? 'CUSTOM_CUSTOMER_TITLE' : `CUSTOM_BLOCK_${index + 1}`,
        occurrences: 1,
      })),
      bookmarks: [],
      tokens: ['{{REPORT_TITLE}}'],
      tokenOccurrences: { '{{REPORT_TITLE}}': 1 },
    },
    mapping: {
      coveragePercent: 0,
      approvedCount: 0,
      requiredCount: 1,
      checklist: [
        {
          semantic: 'report.title',
          required: true,
          status: 'unmapped',
          suggestedAnchors: [
            { kind: 'token', value: '{{REPORT_TITLE}}', confidence: 'exact_name' },
          ],
        },
      ],
    },
  },
  slots: [],
};

const analysis = {
  schemaVersion: '1.0',
  reportType: 'full',
  templateSha256: workspace.templateSha256,
  facts: {
    contentControls: [],
    bookmarks: [],
    tokens: ['{{REPORT_TITLE}}'],
    anchorConflicts: [],
    headings: [{ index: 0, level: 1, text: 'Tổng quan' }],
    tables: [{ index: 0, headers: ['STT', 'Máy trạm'], rowCount: 1 }],
  },
  mapping: workspace.analysis.mapping,
  profileSeed: { status: 'analyzed', slots: [] },
};

test('Template Studio analyzes before creating an isolated workspace', async ({ page }) => {
  let created = false;
  let currentWorkspace = workspace;
  const mutations = [];

  await page.route('**/api/template-packs/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (request.method() === 'GET' && path === '/api/template-packs/workspaces') {
      const archived = url.searchParams.get('archived') === 'true';
      return route.fulfill({
        json: {
          items: created && !archived ? [workspace] : [],
          hasMore: false,
          nextCursor: null,
          skippedCorrupt: 0,
        },
      });
    }
    if (request.method() === 'GET' && path.endsWith(`/workspaces/${workspace.workspaceId}`)) {
      return route.fulfill({ json: currentWorkspace });
    }
    if (request.method() === 'POST' && path.endsWith('/analyze-template')) {
      mutations.push({ kind: 'analyze', body: request.postDataJSON() });
      return route.fulfill({ json: analysis });
    }
    if (request.method() === 'POST' && path === '/api/template-packs/workspaces') {
      mutations.push({ kind: 'create', body: request.postDataJSON() });
      created = true;
      return route.fulfill({ status: 201, json: workspace });
    }
    if (request.method() === 'PUT' && path.endsWith('/mappings/report.title')) {
      const body = request.postDataJSON();
      mutations.push({ kind: 'map', body });
      currentWorkspace = {
        ...workspace,
        revision: 2,
        coveragePercent: 100,
        status: 'mapping_complete',
        slots: [
          {
            semantic: 'report.title',
            renderer: 'text',
            source: 'metadata.title',
            anchor: body.anchor,
            fields: [],
          },
        ],
      };
      return route.fulfill({ json: currentWorkspace });
    }
    return route.fulfill({ status: 404, json: { detail: 'Not mocked' } });
  });

  await page.goto('/?view=template-studio');
  await expect(page.getByRole('heading', { name: 'Chưa có workspace' })).toBeVisible();
  await page.getByRole('button', { name: 'Quản lý workspace' }).click();
  await page.getByRole('button', { name: 'Template mới' }).click();

  await page.locator('input[type="file"][accept=".docx"]').setInputFiles({
    name: 'customer-full.docx',
    mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    buffer: Buffer.from('synthetic-docx-for-ui-contract'),
  });
  await expect(page.getByText('customer-full.docx', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Tạo workspace' })).toBeDisabled();

  await page.getByRole('button', { name: 'Phân tích' }).click();
  await expect(page.getByText('Đã phân tích an toàn')).toBeVisible();
  await expect(page.getByText('0%')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Tạo workspace' })).toBeEnabled();

  await page.getByRole('button', { name: 'Tạo workspace' }).click();
  await expect(page.getByRole('heading', { name: 'Ánh xạ template' })).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Workspace hiện tại' })).toHaveValue(
    workspace.workspaceId,
  );

  await page.getByRole('button', { name: /Tiêu đề báo cáo/ }).click();
  await expect(page.getByRole('searchbox', { name: 'Tìm Word anchor' })).toBeVisible();
  await page.getByRole('searchbox', { name: 'Tìm Word anchor' }).fill('customer title');
  await page
    .getByLabel('Word anchor', { exact: true })
    .selectOption('content_control:CUSTOM_CUSTOMER_TITLE');
  await page.getByRole('button', { name: 'Duyệt ánh xạ' }).click();
  await expect(page.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100');

  expect(mutations.map((item) => item.kind)).toEqual(['analyze', 'create', 'map']);
  expect(mutations[0].body).toMatchObject({
    filename: 'customer-full.docx',
    reportType: 'full',
  });
  expect(mutations[1].body).toMatchObject({
    filename: 'customer-full.docx',
    reportType: 'full',
    profileId: 'customer-full',
    displayName: 'customer-full',
    version: '0.1.0',
  });
  expect(mutations[2].body).toMatchObject({
    anchor: { kind: 'content_control', value: 'CUSTOM_CUSTOMER_TITLE' },
    expectedRevision: 1,
  });
  expect(
    mutations.some((item) => JSON.stringify(item).toLocaleLowerCase().includes('generate')),
  ).toBe(false);
});

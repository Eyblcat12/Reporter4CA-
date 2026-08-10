import { expect, test } from '@playwright/test';

const sampleRows = [
  {
    type: 'server',
    hostname: 'srv-theme-01',
    ip: '10.0.0.10',
    os: 'Windows Server 2022',
    result: 'Clean',
    notes: '',
  },
  {
    type: 'client',
    hostname: 'ws-theme-01',
    ip: '10.0.0.20',
    os: 'Windows 11',
    result: 'Reviewed',
    notes: '',
  },
];

async function readQualityColors(page) {
  return page.locator('.quality-panel').evaluate((panel) => {
    const rgba = (value) => {
      const canvas = document.createElement('canvas');
      canvas.width = 1;
      canvas.height = 1;
      const context = canvas.getContext('2d');
      context.clearRect(0, 0, 1, 1);
      context.fillStyle = value;
      context.fillRect(0, 0, 1, 1);
      return [...context.getImageData(0, 0, 1, 1).data];
    };

    const panelStyle = getComputedStyle(panel);
    const cardStyle = getComputedStyle(panel.querySelector('.quality-card'));
    const titleStyle = getComputedStyle(panel.querySelector('.quality-panel__head strong'));
    return {
      theme: document.documentElement.getAttribute('data-theme'),
      panel: rgba(panelStyle.backgroundColor),
      card: rgba(cardStyle.backgroundColor),
      title: rgba(titleStyle.color),
    };
  });
}

test('Data quality remains readable after switching from dark to light', async ({ page }) => {
  await page.addInitScript(() => {
    if (!localStorage.getItem('reporter-theme')) {
      localStorage.setItem('reporter-theme', 'dark');
    }
  });
  await page.route('**/api/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/api/sample') {
      return route.fulfill({
        json: {
          rows: sampleRows,
          payload: {},
          counts: { servers: 1, clients: 1, total: 2 },
          previewText: 'theme sample',
        },
      });
    }
    if (pathname === '/api/validate-rows') {
      return route.fulfill({
        json: {
          valid: true,
          issues: [],
          summary: {
            totalRows: 2,
            validRows: 2,
            errorRows: 0,
            warningRows: 0,
            errors: 0,
            warnings: 0,
            servers: 1,
            clients: 1,
            duplicateHostnames: 0,
            invalidIps: 0,
            missingOs: 0,
            missingResult: 0,
          },
        },
      });
    }
    if (pathname.startsWith('/api/runtime/browser/')) {
      return route.fulfill({ json: { managedByLauncher: false } });
    }
    if (pathname === '/api/dashboard/summary') {
      return route.fulfill({
        json: { days: 90, metrics: {}, series: [], recent: [] },
      });
    }
    if (pathname === '/api/templates') return route.fulfill({ json: { templates: [] } });
    if (pathname === '/api/presets') return route.fulfill({ json: { presets: [] } });
    if (pathname === '/api/reports/history') return route.fulfill({ json: { reports: [] } });
    return route.fulfill({ status: 404, json: { detail: 'Not mocked' } });
  });

  await page.goto('/');
  await page.getByRole('button', { name: /Tạo báo cáo/i }).click();
  await page.getByRole('button', { name: 'Mẫu' }).click();
  await page.getByRole('button', { name: 'Tiếp tục' }).click();

  const panel = page.locator('.quality-panel');
  await expect(panel).toBeVisible();
  const dark = await readQualityColors(page);
  expect(dark.theme).toBe('dark');
  expect(dark.panel[0] + dark.panel[1] + dark.panel[2]).toBeLessThan(180);

  await page.getByRole('button', { name: 'Toggle theme' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await expect
    .poll(async () => {
      const colors = await readQualityColors(page);
      return colors.panel[0] + colors.panel[1] + colors.panel[2];
    })
    .toBeGreaterThan(700);
  const light = await readQualityColors(page);

  expect(light.card[0] + light.card[1] + light.card[2]).toBeGreaterThan(700);
  expect(light.title[0] + light.title[1] + light.title[2]).toBeLessThan(140);

  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
});

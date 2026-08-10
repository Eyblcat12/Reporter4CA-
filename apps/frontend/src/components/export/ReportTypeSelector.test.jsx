import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import ReportTypeSelector from './ReportTypeSelector';

const setReportSettings = vi.fn();
vi.mock('../../hooks/useReporter', () => ({
  useReporterContext: () => ({
    reportSettings: { reportType: 'full', templatePath: 'full.docx' },
    templates: [{ path: 'technical.docx', reportType: 'technical', isDefault: true }],
    setReportSettings,
  }),
}));
vi.mock('../../i18n', () => ({ useI18n: () => ({ t: (key) => key }) }));

it('switches report type and selects its compatible default template', async () => {
  render(<ReportTypeSelector />);
  await userEvent.click(screen.getByText('export.technical'));
  expect(setReportSettings).toHaveBeenCalledWith(
    expect.objectContaining({
      reportType: 'technical',
      templatePath: 'technical.docx',
    }),
  );
});

import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ReportSettings from './ReportSettings';

const context = {
  reportSettings: { reportType: 'full', templatePath: '' },
  setReportSettings: vi.fn(),
  fetchTemplates: vi.fn(),
  templates: [
    { id: 'ok', name: 'Team cover', path: 'team.docx', reportType: 'full', compatibilityStatus: 'compatible_with_warnings' },
    { id: 'bad', name: 'Broken template', path: 'broken.docx', reportType: 'full', compatibilityStatus: 'incompatible' },
  ],
};

vi.mock('../../hooks/useReporter', async (importOriginal) => ({
  ...(await importOriginal()),
  useReporterContext: () => context,
}));
vi.mock('../../i18n', () => ({ useI18n: () => ({ t: (key) => key }) }));

describe('ReportSettings template compatibility', () => {
  beforeEach(() => {
    context.reportSettings = { reportType: 'full', templatePath: '' };
  });

  it('does not offer an incompatible template for report generation', () => {
    render(<ReportSettings />);
    expect(screen.getByRole('option', { name: /Team cover/ })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: /Broken template/ })).not.toBeInTheDocument();
  });

  it('shows blocking Incident Response readiness issues', () => {
    context.reportSettings = { reportType: 'incident_response', templatePath: '', incidentMetadata: {} };
    render(<ReportSettings />);
    expect(screen.getByText('BLOCKED')).toBeInTheDocument();
    expect(screen.getByText(/3.*lỗi/)).toBeInTheDocument();
    expect(screen.getAllByText(/mã sự cố/i).length).toBeGreaterThan(0);
  });

  it('shows traceability counts when Incident Response data is ready', () => {
    context.reportSettings = {
      reportType: 'incident_response', templatePath: '',
      incidentMetadata: {
        incidentId: 'IR-001', detectedAt: '2026-07-21T09:00',
        timelineText: '09:00 | Alert detected | E-1 | 203.0.113.10',
        iocsText: 'IP | 203.0.113.10 | E-1',
        containmentActions: 'Isolate host | completed | SOC | E-2',
      },
    };
    render(<ReportSettings />);
    expect(screen.getByText('READY')).toBeInTheDocument();
    const stats = [...screen.getByLabelText(/Incident Response/).querySelectorAll('.rs__readiness-stats > span')]
      .map((node) => node.textContent.replace(/\s+/g, ' ').trim());
    expect(stats).toEqual(['1 Timeline', '1 IoC', '1 Actions', '2 Evidence']);
  });
});

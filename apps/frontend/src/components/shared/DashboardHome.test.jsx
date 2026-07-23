import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DashboardHome from './DashboardHome';

let reporter;

vi.mock('../../hooks/useReporter', () => ({ useReporterContext: () => reporter }));
vi.mock('../../i18n', () => ({
  useI18n: () => ({
    locale: 'en',
    t: (key) => ({
      'dashboard.title': 'Overview', 'dashboard.subtitle': 'Workspace activity',
      'dashboard.history': 'History', 'dashboard.newReport': 'New report',
      'dashboard.chooseSource': 'Choose source', 'dashboard.continue': 'Continue',
      'dashboard.source.file': 'File', 'dashboard.source.text': 'Raw text',
      'dashboard.source.sample': 'Sample', 'dashboard.source.fileDesc': 'File description',
      'dashboard.source.textDesc': 'Text description', 'dashboard.source.sampleDesc': 'Sample description',
      'dashboard.metrics': 'Metrics', 'dashboard.reports': 'Reports',
      'dashboard.assets': 'Assets', 'dashboard.success': 'Success',
      'dashboard.completed': 'completed', 'dashboard.noAttempts': 'no attempts',
      'dashboard.noPrevious': 'No previous period', 'dashboard.periodContext': 'selected period',
      'dashboard.assetsContext': 'assets context', 'dashboard.activity': 'Activity',
      'dashboard.period': 'Period', 'dashboard.sixMonths': '6m',
      'dashboard.noActivity': 'No activity', 'dashboard.latestPeriod': 'Latest period',
      'dashboard.recent': 'Recent reports', 'dashboard.viewAll': 'View all',
      'dashboard.showLess': 'Show less', 'dashboard.noReports': 'No reports yet',
      'dashboard.reportSuccess': 'Success', 'dashboard.reportFailed': 'Failed',
      'dashboard.reportCancelled': 'Cancelled',
      'dashboard.untitled': 'Untitled', 'dashboard.ready': 'Ready', 'common.close': 'Close',
    }[key] || key),
  }),
}));

const summary = (overrides = {}) => ({
  days: 90,
  metrics: {
    reports: 3, attempts: 4, failed: 1, assets: 42, reportTypes: 2,
    successRate: 75, avgDurationMs: 120, deltaPercent: 50, ...overrides,
  },
  series: Array.from({ length: 8 }, (_, index) => {
    const start = new Date(Date.now() - (8 - index) * 86400000);
    return {
      start: start.toISOString(),
      end: new Date(start.getTime() + 86400000).toISOString(),
      count: index === 7 ? 3 : 0,
    };
  }),
  recent: [{
    id: 'r1', title: 'Assessment Alpha', report_type: 'full', row_count: 12,
    created_at: new Date().toISOString(),
  }],
});

beforeEach(() => {
  reporter = {
    importFile: vi.fn(), loadSample: vi.fn(), reportHistory: [], dashboardSummary: null,
    fetchReportHistory: vi.fn().mockResolvedValue(null),
    fetchDashboardSummary: vi.fn().mockResolvedValue(null), lastReportId: null, loading: false,
  };
});

describe('DashboardHome', () => {
  it('shows the honest empty state when no history exists', () => {
    render(<DashboardHome />);
    expect(screen.getByText('No reports yet')).toBeInTheDocument();
    expect(screen.getByText('No activity')).toBeInTheDocument();
  });

  it('renders populated server metrics and recent reports', () => {
    reporter.dashboardSummary = summary();
    reporter.dashboardSummary.series[7].end = '2026-07-22T12:00:00.000Z';
    const { container } = render(<DashboardHome />);
    expect(screen.getByText('75%')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('Assessment Alpha')).toBeInTheDocument();
    expect(
      [...container.querySelectorAll('.dashboard-home__y-axis-label')].map((node) => node.textContent),
    ).toEqual(['0', '1', '2', '3', '4']);
    expect(
      [...container.querySelectorAll('.dashboard-home__axis-label')].map((node) => node.textContent),
    ).toContain('Jul 22');
  });

  it('shows the complete report history with date, time and status', async () => {
    const user = userEvent.setup();
    const history = Array.from({ length: 11 }, (_, index) => ({
      id: `r${index + 1}`,
      title: `Assessment ${index + 1}`,
      report_type: 'full',
      row_count: index >= 9 ? 0 : 30,
      status: index === 10 ? 'failed' : index === 9 ? 'cancelled' : 'success',
      created_at: new Date(Date.UTC(2026, 6, 22, 12 - index, 15)).toISOString(),
    }));
    reporter.reportHistory = history;
    reporter.dashboardSummary = { ...summary(), recent: history.slice(0, 8) };
    const { container } = render(<DashboardHome />);

    expect(container.querySelectorAll('.dashboard-home__report')).toHaveLength(4);
    expect(screen.queryByText('Assessment 11')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'View all' }));

    expect(container.querySelectorAll('.dashboard-home__report')).toHaveLength(11);
    expect(screen.getByText('Assessment 11')).toBeInTheDocument();
    expect(screen.getByText(/Failed · full · 0 assets/)).toBeInTheDocument();
    expect(screen.getByText(/Cancelled · full · 0 assets/)).toBeInTheDocument();
    const timestamps = [...container.querySelectorAll('.dashboard-home__report time')].map((node) => node.textContent);
    expect(timestamps).toHaveLength(11);
    expect(timestamps.every((value) => value.includes('2026') && /\d{1,2}:\d{2}/.test(value))).toBe(true);
  });

  it('derives bucket end labels when an older backend only returns bucket starts', () => {
    reporter.dashboardSummary = summary();
    reporter.dashboardSummary.series[7] = {
      start: '2026-07-11T06:00:00.000Z',
      count: 3,
    };
    const { container } = render(<DashboardHome />);
    expect(
      [...container.querySelectorAll('.dashboard-home__axis-label')].map((node) => node.textContent),
    ).toContain('Jul 22');
  });

  it('refreshes history and the active chart period after a report completes', async () => {
    const { rerender } = render(<DashboardHome />);
    await waitFor(() => expect(reporter.fetchDashboardSummary).toHaveBeenCalledWith(90));
    reporter.fetchDashboardSummary.mockClear();
    reporter.fetchReportHistory.mockClear();

    reporter.lastReportId = 'report-new';
    rerender(<DashboardHome />);

    await waitFor(() => expect(reporter.fetchReportHistory).toHaveBeenCalledOnce());
    expect(reporter.fetchDashboardSummary).toHaveBeenCalledWith(90);
  });

  it('keeps actions usable when the summary request fails', () => {
    reporter.fetchDashboardSummary.mockRejectedValue(new Error('offline'));
    render(<DashboardHome />);
    expect(screen.getByRole('button', { name: /New report/i })).toBeEnabled();
    expect(screen.getByText('No reports yet')).toBeInTheDocument();
  });

  it('requests 30, 90 and 180 day periods', async () => {
    const user = userEvent.setup();
    render(<DashboardHome />);
    await waitFor(() => expect(reporter.fetchDashboardSummary).toHaveBeenCalledWith(90));
    await user.click(screen.getByRole('button', { name: '30d' }));
    await user.click(screen.getByRole('button', { name: '6m' }));
    expect(reporter.fetchDashboardSummary).toHaveBeenCalledWith(30);
    expect(reporter.fetchDashboardSummary).toHaveBeenCalledWith(180);
  });

  it('represents failed attempts in the success KPI', () => {
    reporter.dashboardSummary = summary({ reports: 1, attempts: 2, failed: 1, successRate: 50 });
    render(<DashboardHome />);
    expect(screen.getByText('50%')).toBeInTheDocument();
    expect(screen.getByText(/1\/2 completed/)).toBeInTheDocument();
  });

  it('launches raw text and sample sources from the compact selector', async () => {
    const user = userEvent.setup();
    const onOpenImport = vi.fn();
    render(<DashboardHome onOpenImport={onOpenImport} />);
    await user.click(screen.getByRole('button', { name: /New report/i }));
    await user.click(screen.getByRole('button', { name: 'Raw text' }));
    await user.click(screen.getByRole('button', { name: /Continue/i }));
    expect(onOpenImport).toHaveBeenCalledWith('text');

    fireEvent.click(screen.getByRole('button', { name: /New report/i }));
    await user.click(screen.getByRole('button', { name: 'Sample' }));
    await user.click(screen.getByRole('button', { name: /Continue/i }));
    expect(reporter.loadSample).toHaveBeenCalledOnce();
  });
});

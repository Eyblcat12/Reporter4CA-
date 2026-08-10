import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ReportJobPanel from './ReportJobPanel';

const context = {
  activeReportJob: null,
  cancelReportJob: vi.fn(),
  downloadReportJob: vi.fn(),
};

vi.mock('../../hooks/useReporter', () => ({
  useReporterContext: () => context,
}));

vi.mock('../../i18n', () => ({
  useI18n: () => ({ t: (key) => key }),
}));

describe('ReportJobPanel', () => {
  beforeEach(() => {
    context.cancelReportJob.mockReset();
    context.downloadReportJob.mockReset();
    context.activeReportJob = null;
  });

  it('shows progress, supports cancel, and collapses without stopping the job', () => {
    context.activeReportJob = {
      id: 'job-1',
      status: 'running',
      phase: 'generating',
      progress: 45,
      message: 'Generating',
    };
    render(<ReportJobPanel />);

    expect(screen.getByText('45%')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'jobs.cancel' }));
    expect(context.cancelReportJob).toHaveBeenCalledWith('job-1');

    fireEvent.click(screen.getByRole('button', { name: 'common.close' }));
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument();
    expect(screen.getByText('45%')).toBeInTheDocument();
  });

  it('offers the completed artifact for download again', () => {
    context.activeReportJob = {
      id: 'job-2',
      status: 'completed',
      phase: 'completed',
      progress: 100,
      filename: 'assessment.docx',
    };
    render(<ReportJobPanel />);

    fireEvent.click(screen.getByRole('button', { name: 'jobs.downloadAgain' }));
    expect(context.downloadReportJob).toHaveBeenCalledWith(context.activeReportJob);
  });
});

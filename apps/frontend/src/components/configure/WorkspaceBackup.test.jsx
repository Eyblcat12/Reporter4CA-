import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import WorkspaceBackup from './WorkspaceBackup';

const context = {
  downloadWorkspaceBackup: vi.fn(),
  previewWorkspaceRestore: vi.fn(),
  restoreWorkspaceBackup: vi.fn(),
};

vi.mock('../../hooks/useReporter', () => ({ useReporterContext: () => context }));
vi.mock('../../i18n', () => ({ useI18n: () => ({ t: (key) => key }) }));

describe('WorkspaceBackup restore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    context.previewWorkspaceRestore.mockResolvedValue({
      confirmationToken: 'sha256-token',
      archive: { createdAt: '2026-08-03T10:00:00Z' },
      database: {
        records: { templates: 2, presets: 3, report_history: 4, detection_rules: 1 },
      },
      templateCount: 2,
      warnings: [],
    });
    context.restoreWorkspaceBackup.mockResolvedValue({ restored: true, templateCount: 2 });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('runs dry-run and shows the restore contents before enabling restore', async () => {
    const { container } = render(<WorkspaceBackup />);
    const file = new File(['backup'], 'workspace.zip', { type: 'application/zip' });
    fireEvent.change(container.querySelector('input[type="file"]'), {
      target: { files: [file] },
    });

    expect(await screen.findByText('workspace.zip')).toBeInTheDocument();
    expect(screen.getByText('Presets')).toBeInTheDocument();
    expect(screen.getByText('History')).toBeInTheDocument();
    expect(context.previewWorkspaceRestore).toHaveBeenCalledWith(file);
    expect(context.restoreWorkspaceBackup).not.toHaveBeenCalled();
  });

  it('restores only after confirmation using the dry-run token', async () => {
    const { container } = render(<WorkspaceBackup />);
    const file = new File(['backup'], 'workspace.zip', { type: 'application/zip' });
    fireEvent.change(container.querySelector('input[type="file"]'), {
      target: { files: [file] },
    });
    fireEvent.click(await screen.findByRole('button', { name: 'backup.restoreApply' }));

    await waitFor(() => {
      expect(context.restoreWorkspaceBackup).toHaveBeenCalledWith(file, 'sha256-token');
    });
    expect(await screen.findByText('backup.restoreSuccess')).toBeInTheDocument();
  });

  it('surfaces checksum or manifest validation failures without restore controls', async () => {
    context.previewWorkspaceRestore.mockRejectedValueOnce(new Error('Checksum mismatch'));
    const { container } = render(<WorkspaceBackup />);
    const file = new File(['broken'], 'broken.zip', { type: 'application/zip' });
    fireEvent.change(container.querySelector('input[type="file"]'), {
      target: { files: [file] },
    });

    expect(await screen.findByText('Checksum mismatch')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'backup.restoreApply' })).not.toBeInTheDocument();
  });
});

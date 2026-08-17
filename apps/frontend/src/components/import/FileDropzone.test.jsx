import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import FileDropzone from './FileDropzone';

const clearImportedFile = vi.fn();
const context = {
  importedFile: { name: 'Tracking_2.csv', size: 4096 },
  importFile: vi.fn(),
  importProgress: {
    status: 'running',
    phase: 'importing',
    progress: 68,
    message: 'Đang chuẩn hóa và nhập dữ liệu',
    filename: 'Tracking_2.csv',
    rowCount: 0,
  },
  setImportProgress: vi.fn(),
  loadSample: vi.fn(),
  loading: true,
  clearImportedFile,
};

vi.mock('../../hooks/useReporter', () => ({ useReporterContext: () => context }));
vi.mock('../../i18n', () => ({ useI18n: () => ({ t: (key) => key }) }));

describe('FileDropzone import progress', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows a determinate percentage and current import phase', () => {
    render(<FileDropzone />);

    expect(screen.getByRole('progressbar', { name: 'import.progress.label' })).toHaveAttribute(
      'aria-valuenow',
      '68',
    );
    expect(screen.getByText('68%')).toBeInTheDocument();
    expect(screen.getByText('import.progress.importing')).toBeInTheDocument();
    expect(screen.getAllByText('Tracking_2.csv')).toHaveLength(2);
  });

  it('lets the user cancel an import in progress', () => {
    render(<FileDropzone />);

    fireEvent.click(
      screen.getByRole('button', { name: /import\.progress\.cancel Tracking_2\.csv/i }),
    );
    expect(clearImportedFile).toHaveBeenCalledOnce();
  });
});

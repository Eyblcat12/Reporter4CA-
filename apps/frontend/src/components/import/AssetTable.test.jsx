import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AssetTable from './AssetTable';

const startRuleFromRow = vi.fn();
const context = {
  rows: [
    {
      type: 'client',
      hostname: 'PC-NOTE-01',
      ip: '10.0.0.10',
      os: 'Windows 11',
      result: 'Cần xác minh',
      notes: 'Acme Relay detected',
    },
  ],
  addRow: vi.fn(),
  removeRow: vi.fn(),
  updateRow: vi.fn(),
  startRuleFromRow,
  validateRows: vi.fn(),
  dataQuality: {
    valid: true,
    issues: [],
    summary: {
      totalRows: 1,
      validRows: 1,
      errorRows: 0,
      warningRows: 0,
      errors: 0,
      warnings: 0,
      servers: 0,
      clients: 1,
      duplicateHostnames: 0,
      invalidIps: 0,
      missingOs: 0,
      missingResult: 0,
    },
  },
};

vi.mock('../../hooks/useReporter', () => ({ useReporterContext: () => context }));
vi.mock('../../i18n', () => ({ useI18n: () => ({ t: (key) => key }) }));

describe('AssetTable rule shortcut', () => {
  beforeEach(() => vi.clearAllMocks());

  it('starts a rule draft from the selected row note', () => {
    render(<AssetTable />);
    fireEvent.click(screen.getByRole('button', { name: 'Tạo rule từ PC-NOTE-01' }));
    expect(startRuleFromRow).toHaveBeenCalledWith(0, 'notes');
  });
});

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import RuleManager from './RuleManager';

const setReportSettings = vi.fn();
const context = {
  rows: [{ hostname: 'PC-01', notes: 'Acme Relay detected' }],
  detectionRules: [{
    id: 'PROXY_TOOL_REVIEW', name: 'Proxy tool', severity: 'medium',
    classification: 'needs_review', remediation: 'Verify usage', source: 'custom', editable: true,
    conditions: { fields: ['notes'], containsAny: ['proxy'], excludeContainsAny: [] },
  }],
  fetchDetectionRules: vi.fn(),
  reportSettings: { ruleSettings: { disabledRuleIds: [] } },
  setReportSettings,
  saveDetectionRule: vi.fn().mockResolvedValue({ id: 'CUSTOM_1', name: 'Proxy nội bộ' }),
  evaluateDetectionRule: vi.fn().mockResolvedValue({
    matchedRows: 1, totalRows: 1,
    matches: [{ row: 0, hostname: 'PC-01', evidence: [{ field: 'notes', matched: 'acme relay' }] }],
  }),
  fetchDetectionRuleVersions: vi.fn().mockResolvedValue([
    { id: 'v2', versionNumber: 2, createdAt: '2026-07-21T00:00:00Z' },
    { id: 'v1', versionNumber: 1, createdAt: '2026-07-20T00:00:00Z' },
  ]),
  rollbackDetectionRule: vi.fn().mockResolvedValue({
    id: 'PROXY_TOOL_REVIEW', name: 'Proxy tool', severity: 'medium',
    classification: 'needs_review', remediation: 'Verify usage',
    conditions: { fields: ['notes'], containsAny: ['proxy'], excludeContainsAny: [] },
  }),
  detectionRuleConflicts: [{
    ruleIds: ['PROXY_TOOL_REVIEW', 'CUSTOM_2'], sharedFields: ['notes'], sharedTerms: ['proxy'],
  }],
  fetchDetectionRuleConflicts: vi.fn().mockResolvedValue([]),
  cloneDetectionRule: vi.fn().mockResolvedValue({ id: 'CUSTOM_COPY', name: 'Proxy tool (copy)' }),
  exportDetectionRules: vi.fn().mockResolvedValue({ schemaVersion: '1.0', rules: [] }),
  importDetectionRules: vi.fn().mockResolvedValue({ imported: [], skipped: [], errors: [] }),
};

vi.mock('../../hooks/useReporter', () => ({ useReporterContext: () => context }));

describe('RuleManager', () => {
  it('persists a disabled rule in report settings', () => {
    render(<RuleManager />);
    fireEvent.click(screen.getByRole('checkbox'));
    expect(setReportSettings).toHaveBeenCalledWith(expect.objectContaining({
      ruleSettings: { disabledRuleIds: ['PROXY_TOOL_REVIEW'] },
    }));
  });

  it('dry-runs a draft rule against imported rows before saving', async () => {
    render(<RuleManager />);
    fireEvent.click(screen.getByRole('button', { name: /thêm rule/i }));
    fireEvent.change(screen.getByLabelText(/tên rule/i), { target: { value: 'Proxy nội bộ' } });
    fireEvent.change(screen.getByLabelText(/từ khóa cần khớp/i), { target: { value: 'Acme Relay' } });
    fireEvent.click(screen.getByRole('button', { name: /thử trên 1 dòng/i }));
    expect(await screen.findByText(/khớp 1\/1 dòng/i)).toBeInTheDocument();
    expect(context.evaluateDetectionRule).toHaveBeenCalledWith(expect.objectContaining({
      name: 'Proxy nội bộ',
      conditions: expect.objectContaining({ containsAny: ['Acme Relay'] }),
    }));
  });

  it('shows rule history and can rollback without deleting newer versions', async () => {
    render(<RuleManager />);
    fireEvent.click(screen.getByRole('button', { name: /sửa proxy tool/i }));
    expect(await screen.findByText('v2')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /khôi phục/i }));
    expect(context.rollbackDetectionRule).toHaveBeenCalledWith('PROXY_TOOL_REVIEW', 1);
  });

  it('warns about overlaps and clones a rule for safe team customization', async () => {
    render(<RuleManager />);
    expect(screen.getByText(/1 rule chồng lấn/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /clone proxy tool/i }));
    expect(context.cloneDetectionRule).toHaveBeenCalledWith('PROXY_TOOL_REVIEW');
    expect(await screen.findByText(/đã nhân bản/i)).toBeInTheDocument();
  });

  it('exports and imports a portable rule bundle without overwrite mode', async () => {
    const createObjectURL = vi.fn(() => 'blob:rules');
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createObjectURL });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL });
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const { container } = render(<RuleManager />);

    fireEvent.click(screen.getByRole('button', { name: /export/i }));
    expect(await screen.findByText(/đã xuất 0 rule/i)).toBeInTheDocument();
    expect(createObjectURL).toHaveBeenCalled();

    const file = { text: vi.fn().mockResolvedValue(JSON.stringify({ rules: [{ name: 'Team rule' }] })) };
    fireEvent.change(container.querySelector('input[type="file"]'), { target: { files: [file] } });
    expect(await screen.findByText(/đã import 0/i)).toBeInTheDocument();
    expect(context.importDetectionRules).toHaveBeenCalledWith([{ name: 'Team rule' }], 'rename');
    anchorClick.mockRestore();
  });
});

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider } from '../../hooks/useTheme';
import { isTemplateStudioView } from '../../App';
import TemplateStudioWorkbench from './TemplateStudioWorkbench';

beforeEach(() => {
  const values = new Map();
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem: vi.fn((key) => values.get(key) || null),
      setItem: vi.fn((key, value) => values.set(key, String(value))),
      removeItem: vi.fn((key) => values.delete(key)),
      clear: vi.fn(() => values.clear()),
    },
  });
});

const workspace = {
  workspaceId: 'workspace-1',
  displayName: 'Customer Security Assessment',
  reportType: 'full',
  revision: 12,
  status: 'mapping_incomplete',
  analysis: {
    facts: {
      contentControls: [
        { value: 'REPORTER_REMEDIATION', occurrences: 1 },
        { value: 'CUSTOM_CUSTOMER_SECTION', occurrences: 1 },
      ],
      bookmarks: [],
      tokens: ['{{REPORT_TITLE}}'],
      tokenOccurrences: { '{{REPORT_TITLE}}': 1 },
    },
    mapping: {
      checklist: [
        {
          semantic: 'report.title',
          required: true,
          suggestedAnchors: [
            { kind: 'token', value: '{{REPORT_TITLE}}', confidence: 'exact_name' },
          ],
        },
        {
          semantic: 'remediation',
          required: true,
          suggestedAnchors: [
            {
              kind: 'content_control',
              value: 'REPORTER_REMEDIATION',
              confidence: 'exact_name',
            },
          ],
        },
      ],
    },
  },
  slots: [
    {
      semantic: 'report.title',
      renderer: 'text',
      source: 'metadata.title',
      anchor: { kind: 'token', value: '{{REPORT_TITLE}}' },
      fields: [],
    },
  ],
};

const workspaces = [
  {
    workspaceId: workspace.workspaceId,
    profileId: 'customer-full',
    displayName: workspace.displayName,
    version: '0.1.0',
    reportType: 'full',
    status: 'mapping_incomplete',
    archived: false,
    revision: workspace.revision,
    coveragePercent: 50,
    updatedAt: '2026-09-02T10:30:00Z',
  },
];

function renderWorkbench(overrides = {}) {
  const props = {
    status: 'ready',
    error: null,
    workspaces,
    archivedWorkspaces: [],
    workspace,
    onRetry: vi.fn(),
    onSelectWorkspace: vi.fn(),
    onApprove: vi.fn().mockResolvedValue({ ...workspace, revision: 13 }),
    onRemove: vi.fn().mockResolvedValue({ ...workspace, revision: 13 }),
    onRenameWorkspace: vi.fn(),
    onCloneWorkspace: vi.fn(),
    onAnalyzeTemplate: vi.fn(),
    onCreateWorkspace: vi.fn(),
    onSetWorkspaceArchived: vi.fn(),
    onExportWorkspace: vi.fn(),
    onImportWorkspace: vi.fn(),
    onPreviewRetention: vi.fn(),
    onApplyRetention: vi.fn(),
    onRestoreRetention: vi.fn(),
    onLoadCatalog: vi.fn(),
    onPreviewCatalogRecovery: vi.fn(),
    onRecoverCatalog: vi.fn(),
    onSelectCatalogVersion: vi.fn(),
    onListValidationRuns: vi.fn(),
    onCreateValidationRun: vi.fn(),
    onDownloadValidationArtifact: vi.fn(),
    onApproveValidationBaseline: vi.fn(),
    onPublishValidationRun: vi.fn(),
    ...overrides,
  };
  render(
    <ThemeProvider>
      <TemplateStudioWorkbench {...props} />
    </ThemeProvider>,
  );
  return props;
}

describe('Template Studio route boundary', () => {
  it('opens from its isolated view without changing the default report route', () => {
    expect(isTemplateStudioView({ search: '' })).toBe(false);
    expect(isTemplateStudioView({ search: '?view=template-studio' })).toBe(true);
  });
});

describe('Template Studio Workbench', () => {
  it('shows a dense mapping workspace and filters blockers', async () => {
    const user = userEvent.setup();
    renderWorkbench();

    expect(screen.getByRole('heading', { name: 'Ánh xạ template' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Quay lại Reporter Pro' })).toHaveAttribute(
      'href',
      './',
    );
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '50');
    expect(screen.getByText('Luồng mặc định được bảo vệ')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Blocker', pressed: false }));
    const table = screen.getByRole('table');
    expect(within(table).getByText('Gỡ bỏ mã độc')).toBeInTheDocument();
    expect(within(table).queryByText('Tiêu đề báo cáo')).not.toBeInTheDocument();
  });

  it('approves a complete mapping and sends the current revision contract', async () => {
    const user = userEvent.setup();
    const props = renderWorkbench();

    await user.click(screen.getByRole('button', { name: /Gỡ bỏ mã độc/ }));
    await user.selectOptions(
      screen.getByLabelText('Word anchor'),
      'content_control:REPORTER_REMEDIATION',
    );
    await user.type(screen.getByLabelText('Cột Word cho hostname'), 'column:1');
    await user.type(screen.getByLabelText('Cột Word cho ip'), 'column:2');
    await user.type(screen.getByLabelText('Cột Word cho status'), 'column:3');
    await user.click(screen.getByRole('button', { name: 'Duyệt ánh xạ' }));

    await waitFor(() => expect(props.onApprove).toHaveBeenCalledTimes(1));
    expect(props.onApprove).toHaveBeenCalledWith({
      semantic: 'remediation',
      anchor: { kind: 'content_control', value: 'REPORTER_REMEDIATION' },
      fields: [
        { source: 'hostname', target: 'column:1' },
        { source: 'ip', target: 'column:2' },
        { source: 'status', target: 'column:3' },
      ],
    });
    expect(await screen.findByText('Đã lưu')).toBeInTheDocument();
  });

  it('allows a manually selected unique anchor even when it was not suggested', async () => {
    const user = userEvent.setup();
    const props = renderWorkbench();

    await user.click(screen.getByRole('button', { name: /Gỡ bỏ mã độc/ }));
    expect(screen.getByRole('option', { name: /REPORT_TITLE/ })).toBeDisabled();
    await user.selectOptions(
      screen.getByLabelText('Word anchor'),
      'content_control:CUSTOM_CUSTOMER_SECTION',
    );
    await user.type(screen.getByLabelText('Cột Word cho hostname'), 'column:1');
    await user.type(screen.getByLabelText('Cột Word cho ip'), 'column:2');
    await user.type(screen.getByLabelText('Cột Word cho status'), 'column:3');
    await user.click(screen.getByRole('button', { name: 'Duyệt ánh xạ' }));

    await waitFor(() =>
      expect(props.onApprove).toHaveBeenCalledWith(
        expect.objectContaining({
          semantic: 'remediation',
          anchor: { kind: 'content_control', value: 'CUSTOM_CUSTOMER_SECTION' },
        }),
      ),
    );
  });

  it('preserves the local draft when saving fails', async () => {
    const user = userEvent.setup();
    const saveError = Object.assign(new Error('Backend tạm thời không phản hồi.'), {
      conflict: false,
    });
    renderWorkbench({ onApprove: vi.fn().mockRejectedValue(saveError) });

    await user.click(screen.getByRole('button', { name: /Gỡ bỏ mã độc/ }));
    await user.selectOptions(
      screen.getByLabelText('Word anchor'),
      'content_control:REPORTER_REMEDIATION',
    );
    await user.type(screen.getByLabelText('Cột Word cho hostname'), 'column:1');
    await user.type(screen.getByLabelText('Cột Word cho ip'), 'column:2');
    await user.type(screen.getByLabelText('Cột Word cho status'), 'column:3');
    await user.click(screen.getByRole('button', { name: 'Duyệt ánh xạ' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Draft vẫn được giữ');
    expect(screen.getByLabelText('Cột Word cho hostname')).toHaveValue('column:1');
  });

  it('opens workspace management separately and returns focus when closed', async () => {
    const user = userEvent.setup();
    renderWorkbench();

    const trigger = screen.getByRole('button', { name: 'Quản lý' });
    await user.click(trigger);
    expect(screen.getByRole('dialog', { name: 'Workspace' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Đóng quản lý workspace' }));

    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it('opens the isolated catalog and returns focus when closed', async () => {
    const user = userEvent.setup();
    renderWorkbench({
      onLoadCatalog: vi.fn().mockResolvedValue({ revision: 0, packs: {} }),
      onPreviewCatalogRecovery: vi.fn().mockResolvedValue({
        canRecover: false,
        primary: { exists: false, valid: false },
        checkpoint: { exists: false, valid: false },
      }),
    });

    const trigger = screen.getByRole('button', { name: 'Catalog' });
    await user.click(trigger);
    expect(
      await screen.findByRole('dialog', { name: 'Template Pack Catalog' }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Đóng catalog' }));

    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it('opens validation separately and restores focus without entering Generate', async () => {
    const user = userEvent.setup();
    renderWorkbench({
      onListValidationRuns: vi.fn().mockResolvedValue({ items: [], total: 0 }),
      onLoadCatalog: vi.fn().mockResolvedValue({ revision: 0, packs: {} }),
    });

    const trigger = screen.getByRole('button', { name: 'Kiểm thử' });
    await user.click(trigger);
    expect(
      await screen.findByRole('dialog', { name: 'Kiểm thử Template Pack' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Mapping chưa đạt 100%')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Đóng kiểm thử' }));

    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it.each([
    ['loading', 'Đang tải workspace Template Studio'],
    ['empty', 'Chưa có workspace'],
    ['error', 'Không tải được Template Studio'],
  ])('renders a distinct %s state', (status, expected) => {
    renderWorkbench({ status, workspace: status === 'loading' ? null : workspace });
    expect(screen.getByText(expected)).toBeInTheDocument();
  });
});

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
  const view = render(
    <ThemeProvider>
      <TemplateStudioWorkbench {...props} />
    </ThemeProvider>,
  );
  return {
    ...props,
    rerenderWorkspace(next) {
      view.rerender(
        <ThemeProvider>
          <TemplateStudioWorkbench {...props} workspace={next} />
        </ThemeProvider>,
      );
    },
  };
}

describe('Template Studio route boundary', () => {
  it('opens from its isolated view without changing the default report route', () => {
    expect(isTemplateStudioView({ search: '' })).toBe(false);
    expect(isTemplateStudioView({ search: '?view=template-studio' })).toBe(true);
  });
});

describe('Template Studio Workbench', () => {
  it('autosaves an edit without approval and offers persisted recovery', async () => {
    const user = userEvent.setup();
    const draftApi = {
      list: vi.fn().mockResolvedValue({ items: [], nextOffset: null }),
      save: vi.fn().mockResolvedValue({ draftRevision: 1 }),
      retire: vi.fn().mockResolvedValue({}),
    };
    const props = renderWorkbench({
      draftApi,
      workspace: { ...workspace, templateSha256: 'source' },
    });
    await user.click(screen.getByRole('button', { name: /Gỡ bỏ mã độc/ }));
    await user.type(screen.getByLabelText('Cột Word cho hostname'), '1');
    await screen.findByText('Đã lưu nháp · chưa duyệt mapping');
    expect(draftApi.save).toHaveBeenCalledWith(
      workspace.workspaceId,
      expect.any(String),
      expect.objectContaining({
        baseRevision: 12,
        draft: expect.objectContaining({ fields: expect.objectContaining({ hostname: '1' }) }),
      }),
    );
    expect(props.onApprove).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: 'Bỏ bản nháp', exact: true }));
    expect(draftApi.retire).toHaveBeenCalledWith(
      workspace.workspaceId,
      expect.any(String),
      expect.objectContaining({ reason: 'discarded', expectedDraftRevision: 1 }),
    );
    expect(screen.getByLabelText('Cột Word cho hostname')).toHaveValue('');
  });

  it('restores a stale checkpoint without rebasing or approving it', async () => {
    const user = userEvent.setup();
    const record = {
      draftId: 'old',
      sessionId: 'session',
      draftRevision: 2,
      baseRevision: 11,
      templateSha256: 'source',
      semantic: 'remediation',
      workspaceId: workspace.workspaceId,
      stale: true,
      updatedAt: '2026-09-10',
      baseline: { anchorKey: '', fields: {} },
      draft: {
        anchorKey: 'content_control:REPORTER_REMEDIATION',
        fields: { hostname: '1', ip: '2', status: '3' },
      },
    };
    const draftApi = {
      list: vi.fn().mockResolvedValue({ items: [record], nextOffset: null }),
      save: vi.fn(),
      retire: vi.fn(),
    };
    const props = renderWorkbench({
      draftApi,
      workspace: { ...workspace, templateSha256: 'source' },
    });
    await user.click(screen.getByRole('button', { name: /Gỡ bỏ mã độc/ }));
    await user.click(screen.getByText('Bản nháp đã lưu'));
    await user.click(await screen.findByRole('button', { name: 'Khôi phục bản nháp' }));
    expect(screen.getByLabelText('Cột Word cho hostname')).toHaveValue('1');
    expect(screen.getByText('Bản nháp thuộc revision 11')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Duyệt ánh xạ' })).toBeDisabled();
    expect(props.onApprove).not.toHaveBeenCalled();
    expect(draftApi.save).not.toHaveBeenCalled();
  });
  it('finds remediation by its exact underscored token when another anchor is selected', async () => {
    const user = userEvent.setup();
    const testWorkspace = structuredClone(workspace);
    testWorkspace.analysis.facts.tokens.push('{{REMEDIATION_REGISTER}}');
    testWorkspace.analysis.facts.tokenOccurrences['{{REMEDIATION_REGISTER}}'] = 1;
    for (let index = 0; index < 9; index++) {
      testWorkspace.analysis.facts.contentControls.push({
        value: `EXTRA_${index}`,
        occurrences: 1,
      });
    }
    renderWorkbench({ workspace: testWorkspace });
    await user.click(screen.getByRole('button', { name: /Gỡ bỏ mã độc/ }));
    await user.selectOptions(
      screen.getByLabelText('Word anchor'),
      'content_control:CUSTOM_CUSTOMER_SECTION',
    );
    await user.type(screen.getByLabelText('Tìm Word anchor'), '{{REMEDIATION_REGISTER}}');
    expect(screen.getByRole('option', { name: /REMEDIATION_REGISTER/ })).toBeInTheDocument();
  });
  it('accepts plain column numbers and sends canonical targets to the backend', async () => {
    const user = userEvent.setup();
    const props = renderWorkbench();
    await user.click(screen.getByRole('button', { name: /Gỡ bỏ mã độc/ }));
    for (const [index, field] of ['hostname', 'ip', 'status'].entries()) {
      await user.type(screen.getByLabelText(`Cột Word cho ${field}`), String(index + 1));
    }
    await user.click(screen.getByRole('button', { name: 'Duyệt ánh xạ' }));
    expect(props.onApprove).toHaveBeenCalledWith(
      expect.objectContaining({
        fields: [
          { source: 'hostname', target: 'column:1' },
          { source: 'ip', target: 'column:2' },
          { source: 'status', target: 'column:3' },
        ],
      }),
    );
  });
  it('warns before unloading an edited draft and clears the warning after reverting', async () => {
    const user = userEvent.setup();
    renderWorkbench();
    const unload = () => {
      const event = new Event('beforeunload', { cancelable: true });
      window.dispatchEvent(event);
      return event.defaultPrevented;
    };
    expect(unload()).toBe(false);
    await user.click(screen.getByRole('button', { name: /Gỡ bỏ mã độc/ }));
    await user.type(screen.getByLabelText('Cột Word cho hostname'), 'column:1');
    expect(unload()).toBe(true);
    await user.clear(screen.getByLabelText('Cột Word cho hostname'));
    expect(unload()).toBe(false);
  });

  it('keeps the unload warning for a draft in another section', async () => {
    const user = userEvent.setup();
    renderWorkbench();
    await user.click(screen.getByRole('button', { name: /Gỡ bỏ mã độc/ }));
    await user.type(screen.getByLabelText('Cột Word cho hostname'), 'column:1');
    await user.click(screen.getByRole('button', { name: /Tiêu đề báo cáo/ }));
    const event = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
  });

  it('keeps an edited mapping when closing and reopening or switching sections', async () => {
    const user = userEvent.setup();
    renderWorkbench();
    await user.click(screen.getByRole('button', { name: /Gỡ bỏ mã độc/ }));
    await user.type(screen.getByLabelText('Cột Word cho hostname'), 'column:4');
    await user.click(screen.getAllByRole('button', { name: 'Đóng chi tiết ánh xạ' }).at(-1));
    await user.click(screen.getByRole('button', { name: /Tiêu đề báo cáo/ }));
    await user.click(screen.getByRole('button', { name: /Gỡ bỏ mã độc/ }));
    expect(screen.getByLabelText('Cột Word cho hostname')).toHaveValue('column:4');
  });

  it('keeps stale drafts but blocks approval until the user chooses the new revision', async () => {
    const user = userEvent.setup();
    const props = renderWorkbench();
    await user.click(screen.getByRole('button', { name: /Gỡ bỏ mã độc/ }));
    await user.type(screen.getByLabelText('Cột Word cho hostname'), 'column:4');
    props.rerenderWorkspace({ ...workspace, revision: 13 });
    expect(screen.getByLabelText('Cột Word cho hostname')).toHaveValue('column:4');
    expect(screen.getByText('Bản nháp thuộc revision 12')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Duyệt ánh xạ' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Bỏ bản nháp, dùng bản mới' }));
    expect(screen.getByLabelText('Cột Word cho hostname')).toHaveValue('');
  });

  it('does not reuse a draft for a different source document', async () => {
    const user = userEvent.setup();
    const props = renderWorkbench();
    await user.click(screen.getByRole('button', { name: /Gỡ bỏ mã độc/ }));
    await user.type(screen.getByLabelText('Cột Word cho hostname'), 'column:4');
    props.rerenderWorkspace({ ...workspace, templateSha256: 'new-source' });
    await user.click(screen.getByRole('button', { name: /Gỡ bỏ mã độc/ }));
    expect(screen.getByLabelText('Cột Word cho hostname')).toHaveValue('');
  });

  it('blocks duplicate target columns before sending a mapping', async () => {
    const user = userEvent.setup();
    const props = renderWorkbench();
    await user.click(screen.getByRole('button', { name: /Gỡ bỏ mã độc/ }));
    for (const field of ['hostname', 'ip', 'status']) {
      await user.type(screen.getByLabelText(`Cột Word cho ${field}`), 'column:1');
    }
    expect(screen.getByRole('button', { name: 'Duyệt ánh xạ' })).toBeDisabled();
    expect(props.onApprove).not.toHaveBeenCalled();
  });

  it('blocks sparse columns instead of silently shifting data into earlier columns', async () => {
    const user = userEvent.setup();
    const props = renderWorkbench();
    await user.click(screen.getByRole('button', { name: /Gỡ bỏ mã độc/ }));
    for (const [index, field] of ['hostname', 'ip', 'status'].entries()) {
      await user.type(screen.getByLabelText(`Cột Word cho ${field}`), `column:${index * 2 + 1}`);
    }
    expect(screen.getByRole('button', { name: 'Duyệt ánh xạ' })).toBeDisabled();
    expect(props.onApprove).not.toHaveBeenCalled();
  });

  it('opens review after mapping and then the real validation workflow', async () => {
    const user = userEvent.setup();
    const complete = {
      ...workspace,
      status: 'mapping_complete',
      coveragePercent: 100,
      slots: [
        ...workspace.slots,
        {
          semantic: 'remediation',
          anchor: { kind: 'content_control', value: 'REPORTER_REMEDIATION' },
          fields: [],
        },
      ],
    };
    renderWorkbench({
      workspace: complete,
      onListValidationRuns: vi.fn().mockResolvedValue({ items: [] }),
      onLoadCatalog: vi.fn().mockResolvedValue({ packs: {}, revision: 0 }),
    });
    await user.click(screen.getByRole('button', { name: 'Rà soát template' }));
    expect(screen.getByRole('heading', { name: 'Rà soát template' })).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Tạo báo cáo thử' }));
    expect(await screen.findByRole('button', { name: 'Tạo baseline' })).toBeVisible();
  });

  it('allows reviewing incomplete mapping but blocks validation', async () => {
    const user = userEvent.setup();
    renderWorkbench();
    await user.click(screen.getByRole('button', { name: 'Bước 3: Rà soát' }));
    expect(screen.getByRole('heading', { name: 'Rà soát template' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Bước 4: Kiểm thử' })).toBeDisabled();
    expect(screen.getByText(/Còn 1 block chưa ánh xạ/)).toBeVisible();
  });
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
      expectedRevision: 12,
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

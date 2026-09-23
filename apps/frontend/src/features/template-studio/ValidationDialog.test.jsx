import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ValidationDialog from './ValidationDialog';

const baseline = {
  runId: 'a'.repeat(64),
  workspaceId: 'workspace-1',
  workspaceRevision: 12,
  baselineRunId: '',
  createdAt: '2026-09-02T10:00:00Z',
  state: 'baseline_candidate',
  stale: false,
  baselineApproval: null,
  validation: {
    fixtureId: 'pilot-v1',
    artifactSha256: 'b'.repeat(64),
    fixturePassed: true,
    integrityPassed: true,
    structuralPassed: false,
    readyForVisualReview: false,
    issues: [{ code: 'structural.baseline_missing', message: 'Baseline required.' }],
  },
};

const approvedBaseline = {
  ...baseline,
  state: 'baseline_approved',
  baselineApproval: { reviewedBy: 'reviewer@example.test' },
};

const verified = {
  ...baseline,
  runId: 'c'.repeat(64),
  baselineRunId: baseline.runId,
  state: 'ready_for_review',
  validation: {
    ...baseline.validation,
    artifactSha256: 'd'.repeat(64),
    structuralPassed: true,
    readyForVisualReview: true,
    issues: [],
  },
};

const workspace = {
  workspaceId: 'workspace-1',
  profileId: 'customer-summary',
  displayName: 'Customer Summary',
  version: '1.0.0',
  reportType: 'summary',
  status: 'mapping_complete',
  revision: 12,
};

function renderValidation(items = [], overrides = {}) {
  const props = {
    workspace,
    onDismiss: vi.fn(),
    onListRuns: vi.fn().mockResolvedValue({
      items,
      total: items.length,
      hasMore: false,
      skippedCorrupt: 0,
    }),
    onCreateRun: vi.fn().mockResolvedValue(baseline),
    onDownloadArtifact: vi.fn().mockImplementation((_workspaceId, runId) => {
      const run = items.find((item) => item.runId === runId) || baseline;
      return Promise.resolve({
        blob: new Blob(['docx']),
        filename: `validation-${runId.slice(0, 12)}.docx`,
        artifactSha256: run.validation.artifactSha256,
      });
    }),
    onApproveBaseline: vi.fn().mockResolvedValue(approvedBaseline),
    onPublish: vi.fn().mockResolvedValue({ selectionIntegrated: false }),
    onLoadCatalog: vi.fn().mockResolvedValue({ revision: 4, packs: {} }),
    ...overrides,
  };
  render(<ValidationDialog {...props} />);
  return props;
}

beforeEach(() => {
  vi.stubGlobal('URL', {
    createObjectURL: vi.fn(() => 'blob:validation'),
    revokeObjectURL: vi.fn(),
  });
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('Template Studio two-pass validation dialog', () => {
  it('creates a baseline from an explicit JSON fixture', async () => {
    const user = userEvent.setup();
    const props = renderValidation();
    expect(
      await screen.findByRole('heading', { name: 'Tạo baseline cấu trúc' }),
    ).toBeInTheDocument();
    const fileInput = document.querySelector('input[type="file"]');
    const file = new File(
      [JSON.stringify({ rows: [{ hostname: 'PC-01', result: 'Clean' }] })],
      'pilot.json',
      { type: 'application/json' },
    );

    fireEvent.change(fileInput, { target: { files: [file] } });
    expect(await screen.findByText('1 dòng')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Tạo baseline' }));

    await waitFor(() =>
      expect(props.onCreateRun).toHaveBeenCalledWith(
        workspace.workspaceId,
        expect.objectContaining({
          fixtureId: 'pilot',
          baselineRunId: '',
          expectedWorkspaceRevision: 12,
          rows: [{ hostname: 'PC-01', result: 'Clean' }],
        }),
      ),
    );
  });

  it('requires downloading the exact baseline artifact before approval', async () => {
    const user = userEvent.setup();
    const props = renderValidation([baseline]);
    expect(await screen.findByRole('heading', { name: 'Duyệt baseline' })).toBeInTheDocument();
    const approve = screen.getByRole('button', { name: 'Duyệt baseline' });
    expect(approve).toBeDisabled();

    await user.type(screen.getByLabelText('Người duyệt'), 'reviewer@example.test');
    expect(approve).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Tải DOCX để duyệt' }));
    await waitFor(() => expect(approve).toBeEnabled());
    await user.click(approve);

    await waitFor(() =>
      expect(props.onApproveBaseline).toHaveBeenCalledWith(workspace.workspaceId, baseline.runId, {
        expectedWorkspaceRevision: 12,
        reviewer: 'reviewer@example.test',
        artifactSha256: baseline.validation.artifactSha256,
      }),
    );
  });

  it('blocks approval when the downloaded artifact checksum differs', async () => {
    const user = userEvent.setup();
    const props = renderValidation([baseline], {
      onDownloadArtifact: vi.fn().mockResolvedValue({
        blob: new Blob(['tampered']),
        filename: 'validation.docx',
        artifactSha256: 'f'.repeat(64),
      }),
    });
    expect(await screen.findByRole('heading', { name: 'Duyệt baseline' })).toBeInTheDocument();
    await user.type(screen.getByLabelText('Người duyệt'), 'reviewer@example.test');
    await user.click(screen.getByRole('button', { name: 'Tải DOCX để duyệt' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Checksum artifact tải về không khớp',
    );
    expect(screen.getByRole('button', { name: 'Duyệt baseline' })).toBeDisabled();
    expect(props.onApproveBaseline).not.toHaveBeenCalled();
  });

  it('binds the second pass to the approved baseline and fixture id', async () => {
    const user = userEvent.setup();
    const props = renderValidation([approvedBaseline]);
    expect(await screen.findByRole('heading', { name: 'Chạy lượt xác minh' })).toBeInTheDocument();
    const file = new File([JSON.stringify([{ hostname: 'PC-01' }])], 'new-name.json');

    fireEvent.change(document.querySelector('input[type="file"]'), {
      target: { files: [file] },
    });
    await user.click(await screen.findByRole('button', { name: 'Chạy lượt xác minh' }));

    await waitFor(() =>
      expect(props.onCreateRun).toHaveBeenCalledWith(
        workspace.workspaceId,
        expect.objectContaining({
          fixtureId: 'pilot-v1',
          baselineRunId: approvedBaseline.runId,
        }),
      ),
    );
  });

  it('publishes only the reviewed second-pass checksum at the current catalog revision', async () => {
    const user = userEvent.setup();
    const props = renderValidation([verified, approvedBaseline]);
    expect(await screen.findByRole('heading', { name: 'Duyệt và phát hành' })).toBeInTheDocument();

    await user.type(screen.getByLabelText('Người duyệt'), 'publisher@example.test');
    await user.click(screen.getByRole('button', { name: 'Tải DOCX để duyệt' }));
    const publish = screen.getByRole('button', { name: 'Phát hành vào Catalog' });
    await waitFor(() => expect(publish).toBeEnabled());
    await user.click(publish);

    await waitFor(() =>
      expect(props.onPublish).toHaveBeenCalledWith(workspace.workspaceId, verified.runId, {
        expectedWorkspaceRevision: 12,
        expectedCatalogRevision: 4,
        reviewer: 'publisher@example.test',
        artifactSha256: verified.validation.artifactSha256,
      }),
    );
    expect(screen.getByText(/Configure → Template/)).toBeInTheDocument();
  });

  it('ignores stale runs and blocks validation before mapping is complete', async () => {
    renderValidation([{ ...approvedBaseline, stale: true }], {
      workspace: { ...workspace, status: 'mapping_incomplete' },
    });

    expect(await screen.findByText('Mapping chưa đạt 100%')).toBeInTheDocument();
    expect(screen.getByText('Đã cũ')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Tạo baseline' })).not.toBeInTheDocument();
  });
});

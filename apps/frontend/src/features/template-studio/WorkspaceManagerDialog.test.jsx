import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import WorkspaceManagerDialog from './WorkspaceManagerDialog';

const active = {
  workspaceId: 'active-1',
  profileId: 'customer-full',
  displayName: 'Customer Full',
  version: '0.1.0',
  reportType: 'full',
  status: 'mapping_incomplete',
  archived: false,
  revision: 4,
  coveragePercent: 60,
  updatedAt: '2026-09-02T10:30:00Z',
};

const archived = {
  ...active,
  workspaceId: 'archived-1',
  profileId: 'customer-server-old',
  displayName: 'Customer Server Old',
  reportType: 'server_only',
  archived: true,
  revision: 7,
  coveragePercent: 25,
};

function renderManager(overrides = {}) {
  const props = {
    activeWorkspaces: [active],
    archivedWorkspaces: [archived],
    currentWorkspaceId: active.workspaceId,
    onDismiss: vi.fn(),
    onOpenWorkspace: vi.fn().mockResolvedValue(undefined),
    onRename: vi.fn().mockResolvedValue(undefined),
    onClone: vi.fn().mockResolvedValue(undefined),
    onAnalyzeTemplate: vi.fn().mockResolvedValue({}),
    onCreateWorkspace: vi.fn().mockResolvedValue({ workspaceId: 'workspace-new' }),
    onSetArchived: vi.fn().mockResolvedValue(undefined),
    onExport: vi.fn().mockResolvedValue({
      filename: 'customer-full-4.rptdraft',
      contentBase64: 'UEs=',
    }),
    onImport: vi.fn().mockResolvedValue(undefined),
    onPreviewRetention: vi.fn().mockResolvedValue({
      blocked: false,
      blockers: [],
      candidateWorkspaceCount: 1,
      candidateSourceCount: 1,
      reclaimableBytes: 1536,
      confirmationToken: 'a'.repeat(64),
    }),
    onApplyRetention: vi.fn().mockResolvedValue({
      quarantineId: '0123456789abcdef',
      workspaceCount: 1,
      sourceCount: 1,
      recoverable: true,
      permanentDelete: false,
    }),
    onRestoreRetention: vi.fn().mockResolvedValue({ restored: true }),
    ...overrides,
  };
  const result = render(<WorkspaceManagerDialog {...props} />);
  return { ...result, props };
}

describe('Template Studio workspace manager', () => {
  it('renames with the selected optimistic revision summary', async () => {
    const user = userEvent.setup();
    const { props } = renderManager();

    await user.click(screen.getByRole('button', { name: 'Đổi tên' }));
    const input = screen.getByLabelText('Tên hiển thị');
    await user.clear(input);
    await user.type(input, 'Customer Full Reviewed');
    await user.click(screen.getByRole('button', { name: 'Lưu tên' }));

    await waitFor(() =>
      expect(props.onRename).toHaveBeenCalledWith(active, 'Customer Full Reviewed'),
    );
  });

  it('clones without changing the source workspace', async () => {
    const user = userEvent.setup();
    const { props } = renderManager();

    await user.click(screen.getByRole('button', { name: 'Tạo bản sao' }));
    await user.clear(screen.getByLabelText('Profile ID'));
    await user.type(screen.getByLabelText('Profile ID'), 'customer-full-team');
    await user.click(screen.getByRole('button', { name: 'Tạo bản sao' }));

    await waitFor(() =>
      expect(props.onClone).toHaveBeenCalledWith(
        active,
        expect.objectContaining({ profileId: 'customer-full-team', version: '0.1.0' }),
      ),
    );
  });

  it('requires confirmation before archiving and supports restore', async () => {
    const user = userEvent.setup();
    const { props } = renderManager();

    await user.click(screen.getByRole('button', { name: 'Lưu trữ' }));
    expect(screen.getByRole('alert')).toHaveTextContent('không bị xóa');
    await user.click(within(screen.getByRole('alert')).getByRole('button', { name: 'Lưu trữ' }));
    await waitFor(() => expect(props.onSetArchived).toHaveBeenCalledWith(active, true));

    await user.click(screen.getByRole('tab', { name: /Đã lưu trữ/ }));
    await user.click(screen.getByRole('button', { name: 'Khôi phục' }));
    await user.click(within(screen.getByRole('alert')).getByRole('button', { name: 'Khôi phục' }));
    await waitFor(() => expect(props.onSetArchived).toHaveBeenCalledWith(archived, false));
  });

  it('imports a bounded rptdraft file and rejects an unrelated extension', async () => {
    const { container, props } = renderManager();
    const input = container.querySelector('input[type="file"]');
    const valid = new File(['draft'], 'team.rptdraft', { type: 'application/zip' });

    fireEvent.change(input, { target: { files: [valid] } });
    await waitFor(() =>
      expect(props.onImport).toHaveBeenCalledWith(
        expect.objectContaining({ filename: 'team.rptdraft' }),
      ),
    );

    const invalid = new File(['draft'], 'team.zip', { type: 'application/zip' });
    fireEvent.change(input, { target: { files: [invalid] } });
    expect(await screen.findByRole('alert')).toHaveTextContent('Chỉ chấp nhận tệp .rptdraft');
  });

  it('filters the active table without hiding the archived count', async () => {
    const user = userEvent.setup();
    renderManager({
      activeWorkspaces: [
        active,
        { ...active, workspaceId: 'active-2', displayName: 'Incident Review' },
      ],
    });

    await user.type(screen.getByLabelText('Tìm workspace'), 'incident');
    expect(screen.getAllByText('Incident Review')).toHaveLength(2);
    expect(screen.queryByText('Customer Full')).not.toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Đã lưu trữ 1/ })).toBeInTheDocument();
  });

  it('previews retention before applying a recoverable quarantine', async () => {
    const user = userEvent.setup();
    const { props } = renderManager();

    await user.click(screen.getByRole('button', { name: 'Dọn an toàn' }));
    expect(screen.getByText(/Không xóa vĩnh viễn\./)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Xem trước' }));

    await waitFor(() => expect(props.onPreviewRetention).toHaveBeenCalledWith(90));
    expect(props.onApplyRetention).not.toHaveBeenCalled();
    expect(screen.getByText('1.5 KB')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Chuyển vào cách ly' }));
    await waitFor(() => expect(props.onApplyRetention).toHaveBeenCalledWith('a'.repeat(64)));
    expect(screen.getByText('Đã chuyển vào vùng cách ly')).toBeInTheDocument();
  });

  it('opens the new template workflow even when no workspace exists', async () => {
    const user = userEvent.setup();
    renderManager({ activeWorkspaces: [], archivedWorkspaces: [], currentWorkspaceId: '' });

    await user.click(screen.getByRole('button', { name: 'Template mới' }));

    expect(screen.getByRole('heading', { name: 'Tạo workspace mới' })).toBeInTheDocument();
    expect(screen.getByText('Chưa có kết quả phân tích')).toBeInTheDocument();
  });

  it('restores the quarantine batch without exposing a permanent-delete action', async () => {
    const user = userEvent.setup();
    const { props } = renderManager();

    await user.click(screen.getByRole('button', { name: 'Dọn an toàn' }));
    await user.click(screen.getByRole('button', { name: 'Xem trước' }));
    await user.click(await screen.findByRole('button', { name: 'Chuyển vào cách ly' }));
    await user.click(await screen.findByRole('button', { name: 'Khôi phục ngay' }));

    await waitFor(() => expect(props.onRestoreRetention).toHaveBeenCalledWith('0123456789abcdef'));
    expect(screen.queryByRole('button', { name: /xóa/i })).not.toBeInTheDocument();
  });

  it('shows retention blockers and does not offer apply', async () => {
    const user = userEvent.setup();
    const { props } = renderManager({
      activeWorkspaces: [],
      archivedWorkspaces: [],
      currentWorkspaceId: '',
      onPreviewRetention: vi.fn().mockResolvedValue({
        blocked: true,
        blockers: ['Catalog đang tham chiếu source này.'],
        candidateWorkspaceCount: 2,
        candidateSourceCount: 1,
        reclaimableBytes: 2048,
        confirmationToken: null,
      }),
    });

    await user.click(screen.getByRole('button', { name: 'Dọn an toàn' }));
    await user.click(screen.getByRole('button', { name: 'Xem trước' }));

    expect(await screen.findByText('Không thể áp dụng')).toBeInTheDocument();
    expect(screen.getByText('Catalog đang tham chiếu source này.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Chuyển vào cách ly' })).not.toBeInTheDocument();
    expect(props.onApplyRetention).not.toHaveBeenCalled();
  });
});

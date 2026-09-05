import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import NewTemplateWorkspace from './NewTemplateWorkspace';

const analysis = {
  templateSha256: 'a'.repeat(64),
  facts: {
    contentControls: [{ value: 'REPORT_TITLE' }],
    bookmarks: [{ value: 'ASSET_TABLE' }],
    tokens: ['{{CUSTOMER}}'],
    headings: [{ level: 1, text: 'Tổng quan' }],
    tables: [{ index: 0 }],
    anchorConflicts: [],
  },
  mapping: {
    coveragePercent: 0,
    requiredCount: 2,
    approvedCount: 0,
    checklist: [
      { semantic: 'report.title', suggestedAnchors: [{ kind: 'content_control' }] },
      { semantic: 'assets', suggestedAnchors: [] },
    ],
  },
};

function renderCreator(overrides = {}) {
  const props = {
    onCancel: vi.fn(),
    onAnalyze: vi.fn().mockResolvedValue(analysis),
    onCreate: vi.fn().mockResolvedValue({ workspaceId: 'workspace-new' }),
    ...overrides,
  };
  const result = render(<NewTemplateWorkspace {...props} />);
  return { ...result, props };
}

describe('Template Studio new workspace flow', () => {
  it('requires analysis before creating an explicitly unmapped workspace', async () => {
    const user = userEvent.setup();
    const { container, props } = renderCreator();
    const file = new File(['word-package'], 'customer-full.docx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    });

    expect(screen.getByRole('button', { name: 'Tạo workspace' })).toBeDisabled();
    fireEvent.change(container.querySelector('input[type="file"]'), {
      target: { files: [file] },
    });
    await screen.findByText('customer-full.docx');

    expect(screen.getByRole('button', { name: 'Tạo workspace' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Phân tích' }));

    await waitFor(() =>
      expect(props.onAnalyze).toHaveBeenCalledWith(
        expect.objectContaining({ filename: 'customer-full.docx', reportType: 'full' }),
      ),
    );
    expect(await screen.findByText('Đã phân tích an toàn')).toBeInTheDocument();
    expect(screen.getByText('0%')).toBeInTheDocument();
    expect(screen.getByText(/mọi mapping vẫn cần người dùng duyệt/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Tạo workspace' }));
    await waitFor(() =>
      expect(props.onCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          filename: 'customer-full.docx',
          reportType: 'full',
          profileId: 'customer-full',
          displayName: 'customer-full',
          version: '0.1.0',
        }),
      ),
    );
  });

  it('invalidates analysis when report type changes', async () => {
    const user = userEvent.setup();
    const { container, props } = renderCreator();
    fireEvent.change(container.querySelector('input[type="file"]'), {
      target: { files: [new File(['word'], 'template.docx')] },
    });
    await screen.findByText('template.docx');
    await user.click(screen.getByRole('button', { name: 'Phân tích' }));
    await screen.findByText('Đã phân tích an toàn');

    await user.selectOptions(screen.getByLabelText('Report type'), 'server_only');

    expect(screen.queryByText('Đã phân tích an toàn')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Tạo workspace' })).toBeDisabled();
    expect(props.onCreate).not.toHaveBeenCalled();
  });

  it('preserves the analyzed form when workspace creation fails', async () => {
    const user = userEvent.setup();
    const { container } = renderCreator({
      onCreate: vi.fn().mockRejectedValue(new Error('Profile ID đã tồn tại.')),
    });
    fireEvent.change(container.querySelector('input[type="file"]'), {
      target: { files: [new File(['word'], 'template.docx')] },
    });
    await screen.findByText('template.docx');
    await user.click(screen.getByRole('button', { name: 'Phân tích' }));
    await screen.findByText('Đã phân tích an toàn');
    await user.click(screen.getByRole('button', { name: 'Tạo workspace' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Profile ID đã tồn tại.');
    expect(screen.getByLabelText('Tên hiển thị')).toHaveValue('template');
    expect(screen.getByLabelText(/^Profile ID/)).toHaveValue('template');
    expect(screen.getByText('Đã phân tích an toàn')).toBeInTheDocument();
  });
});

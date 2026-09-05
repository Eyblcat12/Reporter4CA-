import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CatalogDialog from './CatalogDialog';

const healthyRecovery = {
  canRecover: false,
  confirmationToken: '',
  primary: { exists: true, valid: true, revision: 5 },
  checkpoint: { exists: true, valid: true, revision: 4 },
  legacyRendererUnchanged: true,
};

function renderCatalog(overrides = {}) {
  const props = {
    onDismiss: vi.fn(),
    onLoad: vi.fn().mockResolvedValue({
      revision: 5,
      packs: {
        'customer-summary': {
          activeVersion: '1.0.0',
          versions: {
            '1.0.0': {
              displayName: 'Customer Summary',
              reportType: 'summary',
              state: 'installed',
            },
          },
        },
      },
    }),
    onPreviewRecovery: vi.fn().mockResolvedValue(healthyRecovery),
    onRecover: vi.fn().mockResolvedValue({ restoredRevision: 4 }),
    onSelectVersion: vi.fn().mockResolvedValue({ revision: 6 }),
    ...overrides,
  };
  render(<CatalogDialog {...props} />);
  return props;
}

describe('Template Pack catalog dialog', () => {
  it('shows immutable versions and catalog health without touching Generate', async () => {
    renderCatalog();

    expect(await screen.findByText('Customer Summary')).toBeInTheDocument();
    expect(screen.getByText('Đang chọn')).toBeInTheDocument();
    expect(screen.getAllByText('Hợp lệ')).toHaveLength(2);
    expect(screen.getByText('Legacy Renderer không thay đổi')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Khôi phục checkpoint' })).not.toBeInTheDocument();
  });

  it('requires preview-backed confirmation before catalog recovery', async () => {
    const user = userEvent.setup();
    const recoveryNeeded = {
      canRecover: true,
      confirmationToken: 'b'.repeat(64),
      primary: { exists: true, valid: false, revision: null },
      checkpoint: { exists: true, valid: true, revision: 4 },
      legacyRendererUnchanged: true,
    };
    const props = renderCatalog({
      onPreviewRecovery: vi
        .fn()
        .mockResolvedValueOnce(recoveryNeeded)
        .mockResolvedValue(healthyRecovery),
    });

    await user.click(await screen.findByRole('button', { name: 'Khôi phục checkpoint' }));
    expect(props.onRecover).not.toHaveBeenCalled();
    const confirmation = screen.getByRole('alert');
    await user.click(within(confirmation).getByRole('button', { name: 'Xác nhận' }));

    await waitFor(() => expect(props.onRecover).toHaveBeenCalledWith('b'.repeat(64)));
    expect(await screen.findByText(/Catalog đã được khôi phục/)).toBeInTheDocument();
  });

  it('returns focus to the dialog title and closes with Escape', async () => {
    const user = userEvent.setup();
    const props = renderCatalog();

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Template Pack Catalog' })).toHaveFocus(),
    );
    await user.keyboard('{Escape}');
    expect(props.onDismiss).toHaveBeenCalledTimes(1);
  });

  it('confirms isolated activation with the current catalog revision', async () => {
    const user = userEvent.setup();
    const props = renderCatalog({
      onLoad: vi.fn().mockResolvedValue({
        revision: 5,
        packs: {
          'customer-summary': {
            activeVersion: '1.0.0',
            versions: {
              '1.0.0': { displayName: 'Customer Summary', reportType: 'summary' },
              '2.0.0': { displayName: 'Customer Summary', reportType: 'summary' },
            },
          },
        },
      }),
    });

    await user.click(await screen.findByRole('button', { name: 'Kích hoạt' }));
    expect(screen.getByRole('alert')).toHaveTextContent('không thay template Generate');
    await user.click(within(screen.getByRole('alert')).getByRole('button', { name: 'Xác nhận' }));

    await waitFor(() =>
      expect(props.onSelectVersion).toHaveBeenCalledWith(
        'customer-summary',
        '2.0.0',
        5,
        'activate',
      ),
    );
    expect(await screen.findByText(/Generate mặc định không thay đổi/)).toBeInTheDocument();
  });

  it('records an older selection as rollback', async () => {
    const user = userEvent.setup();
    const props = renderCatalog({
      onLoad: vi.fn().mockResolvedValue({
        revision: 8,
        packs: {
          'customer-summary': {
            activeVersion: '2.0.0',
            versions: {
              '1.0.0': { displayName: 'Customer Summary', reportType: 'summary' },
              '2.0.0': { displayName: 'Customer Summary', reportType: 'summary' },
            },
          },
        },
      }),
    });

    await user.click(await screen.findByRole('button', { name: 'Rollback' }));
    await user.click(within(screen.getByRole('alert')).getByRole('button', { name: 'Xác nhận' }));

    await waitFor(() =>
      expect(props.onSelectVersion).toHaveBeenCalledWith(
        'customer-summary',
        '1.0.0',
        8,
        'rollback',
      ),
    );
  });
});

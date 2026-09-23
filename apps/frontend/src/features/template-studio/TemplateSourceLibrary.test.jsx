import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TemplateSourceLibrary from './TemplateSourceLibrary';
import * as api from './templateStudioApi';

vi.mock('./templateStudioApi', () => ({
  listTemplateLibrary: vi.fn(),
  getTemplateLibraryEntry: vi.fn(),
}));
const item = {
  sha256: 'a'.repeat(64),
  filename: 'Customer.docx',
  size_bytes: 1024,
  reportTypes: ['full'],
  updated_at: '2026-09-06T10:00:00Z',
};
beforeEach(() => {
  vi.resetAllMocks();
});

it('loads saved source without approving or reusing old mapping', async () => {
  api.listTemplateLibrary.mockResolvedValue({ items: [item], total: 1 });
  api.getTemplateLibraryEntry.mockResolvedValue({ filename: item.filename, contentBase64: 'YQ==' });
  const onSelect = vi.fn();
  render(<TemplateSourceLibrary onSelect={onSelect} onCancel={vi.fn()} />);
  await userEvent.click(await screen.findByRole('button', { name: /Customer.docx/ }));
  await waitFor(() =>
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ filename: item.filename, contentBase64: 'YQ==' }),
    ),
  );
});

it('recovers after API errors and reports partial migration', async () => {
  api.listTemplateLibrary
    .mockRejectedValueOnce(new Error('Backend offline'))
    .mockResolvedValue({ items: [], total: 0, backfillSkipped: 1 });
  render(<TemplateSourceLibrary onSelect={vi.fn()} onCancel={vi.fn()} />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Backend offline');
  await userEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
  expect(await screen.findByText(/1 workspace cũ/)).toBeInTheDocument();
  expect(screen.getByText(/Chưa có template/)).toBeInTheDocument();
});

it('searches and paginates without submitting the parent workspace form', async () => {
  api.listTemplateLibrary.mockResolvedValue({ items: [item], total: 21, hasMore: true });
  const user = userEvent.setup();
  const submit = vi.fn((event) => event.preventDefault());
  render(
    <form onSubmit={submit}>
      <TemplateSourceLibrary onSelect={vi.fn()} onCancel={vi.fn()} />
    </form>,
  );
  await screen.findByText('21 template đã lưu');
  await user.click(screen.getByRole('button', { name: 'Trang sau' }));
  await waitFor(() =>
    expect(api.listTemplateLibrary).toHaveBeenLastCalledWith(
      expect.objectContaining({ offset: 20 }),
    ),
  );
  await user.type(screen.getByRole('textbox'), 'customer{Enter}');
  await waitFor(() =>
    expect(api.listTemplateLibrary).toHaveBeenLastCalledWith(
      expect.objectContaining({ offset: 0, q: 'customer' }),
    ),
  );
  expect(submit).not.toHaveBeenCalled();
});

it('keeps source choice available after a failed download', async () => {
  api.listTemplateLibrary.mockResolvedValue({ items: [item], total: 1 });
  api.getTemplateLibraryEntry
    .mockRejectedValueOnce(new Error('Checksum invalid'))
    .mockResolvedValue({ filename: item.filename, contentBase64: 'YQ==' });
  const onSelect = vi.fn();
  render(<TemplateSourceLibrary onSelect={onSelect} onCancel={vi.fn()} />);
  await userEvent.click(await screen.findByRole('button', { name: /Customer.docx/ }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Checksum invalid');
  expect(onSelect).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button', { name: /Customer.docx/ }));
  await waitFor(() => expect(onSelect).toHaveBeenCalledTimes(1));
});

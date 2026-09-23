import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import NormalizeDialog from './NormalizeDialog';
import { getTemplateStructure, normalizeTemplateWorkspace } from './templateStudioApi';

vi.mock('./templateStudioApi', () => ({
  getTemplateStructure: vi.fn(),
  normalizeTemplateWorkspace: vi.fn(),
}));
it('requires explicit placement and opens a separate normalized draft', async () => {
  const user = userEvent.setup();
  getTemplateStructure.mockResolvedValue({
    revision: 2,
    blocks: [{ index: 0, kind: 'paragraph', text: 'Customer title' }],
  });
  normalizeTemplateWorkspace.mockResolvedValue({ workspaceId: 'copy' });
  const onCreated = vi.fn();
  const onDismiss = vi.fn();
  render(
    <NormalizeDialog
      workspace={{
        workspaceId: 'original',
        analysis: { mapping: { checklist: [{ semantic: 'report.title' }] } },
      }}
      onCreated={onCreated}
      onDismiss={onDismiss}
    />,
  );
  const submit = screen.getByRole('button', { name: 'Tạo bản chuẩn hóa' });
  expect(submit).toBeDisabled();
  await user.selectOptions(await screen.findByLabelText('Vị trí report.title'), '0');
  await user.selectOptions(screen.getByLabelText('Chế độ report.title'), 'replace');
  await user.click(submit);
  await waitFor(() => expect(onCreated).toHaveBeenCalledWith({ workspaceId: 'copy' }));
  expect(normalizeTemplateWorkspace).toHaveBeenCalledWith('original', {
    expectedRevision: 2,
    placements: [{ semantic: 'report.title', blockIndex: 0, mode: 'replace' }],
  });
  expect(onDismiss).toHaveBeenCalled();
});

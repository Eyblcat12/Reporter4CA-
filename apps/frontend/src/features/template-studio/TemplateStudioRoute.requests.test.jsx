import { act, render, waitFor } from '@testing-library/react';
import TemplateStudioRoute from './TemplateStudioRoute';
import * as api from './templateStudioApi';

let props;
vi.mock('./TemplateStudioWorkbench', () => ({
  default: (value) => {
    props = value;
    return null;
  },
}));
vi.mock('./templateStudioApi', async (importOriginal) => ({
  ...(await importOriginal()),
  listAllTemplateWorkspaces: vi.fn(),
  getTemplateWorkspace: vi.fn(),
  approveTemplateMapping: vi.fn(),
  removeTemplateMapping: vi.fn(),
}));
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((a, b) => {
    resolve = a;
    reject = b;
  });
  return { promise, resolve, reject };
};
const a = { workspaceId: 'a', revision: 1, coveragePercent: 50 };
beforeEach(() => {
  vi.clearAllMocks();
  api.listAllTemplateWorkspaces.mockResolvedValue({ items: [a] });
  api.getTemplateWorkspace.mockResolvedValue(a);
});
async function ready() {
  render(<TemplateStudioRoute />);
  await waitFor(() => expect(props.status).toBe('ready'));
}

it('ignores a late workspace response after a newer selection succeeds', async () => {
  await ready();
  const slow = deferred();
  api.getTemplateWorkspace.mockImplementation((id) =>
    id === 'slow' ? slow.promise : Promise.resolve({ workspaceId: id, revision: 1 }),
  );
  let oldRequest;
  act(() => {
    oldRequest = props.onSelectWorkspace('slow');
  });
  await act(async () => {
    await props.onSelectWorkspace('new');
  });
  await act(async () => {
    slow.resolve({ workspaceId: 'slow', revision: 1 });
    await oldRequest;
  });
  expect(props.workspace.workspaceId).toBe('new');
  expect(props.status).toBe('ready');
});

it('ignores a late read error after a newer selection succeeds', async () => {
  await ready();
  const slow = deferred();
  api.getTemplateWorkspace.mockImplementation((id) =>
    id === 'slow' ? slow.promise : Promise.resolve({ workspaceId: id, revision: 1 }),
  );
  let oldRequest;
  act(() => {
    oldRequest = props.onSelectWorkspace('slow');
  });
  await act(async () => {
    await props.onSelectWorkspace('new');
  });
  await act(async () => {
    slow.reject(new Error('Offline'));
    await oldRequest;
  });
  expect(props.workspace.workspaceId).toBe('new');
  expect(props.error).toBeNull();
});

it('does not replace another workspace with a late approval response', async () => {
  await ready();
  const slow = deferred();
  api.approveTemplateMapping.mockReturnValue(slow.promise);
  let write;
  act(() => {
    write = props.onApprove({ semantic: 'title', anchor: {}, fields: [] });
  });
  api.getTemplateWorkspace.mockResolvedValue({ workspaceId: 'b', revision: 1 });
  await act(async () => {
    await props.onSelectWorkspace('b');
  });
  await act(async () => {
    slow.resolve({ ...a, revision: 2, coveragePercent: 100 });
    await write;
  });
  expect(props.workspace.workspaceId).toBe('b');
  expect(props.workspaces[0].revision).toBe(2);
});

it('updates catalog summary after removing a mapping', async () => {
  await ready();
  api.removeTemplateMapping.mockResolvedValue({
    ...a,
    revision: 2,
    coveragePercent: 0,
    status: 'mapping_incomplete',
  });
  await act(async () => {
    await props.onRemove('title');
  });
  expect(props.workspace.coveragePercent).toBe(0);
  expect(props.workspaces[0].coveragePercent).toBe(0);
});

it('sends the draft revision unchanged instead of rebasing it to the loaded workspace', async () => {
  await ready();
  api.approveTemplateMapping.mockResolvedValue({ ...a, revision: 2 });
  await act(async () => {
    await props.onApprove({ semantic: 'title', anchor: {}, fields: [], expectedRevision: 0 });
  });
  expect(api.approveTemplateMapping).toHaveBeenCalledWith(
    'a',
    'title',
    expect.objectContaining({ expectedRevision: 0 }),
  );
});

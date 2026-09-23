import { createCheckpointQueue } from './editorCheckpointQueue';

const context = {
  workspaceId: 'w',
  templateSha256: 'sha',
  semantic: 'remediation',
  baseRevision: 12,
  baseline: { anchorKey: '', fields: {} },
};
const draft = (value) => ({ anchorKey: 'token:{{R}}', fields: { hostname: value } });
function setup() {
  const api = {
    save: vi.fn(async (_w, _id, p) => ({ draftRevision: p.expectedDraftRevision + 1 })),
    retire: vi.fn(async () => ({})),
  };
  let sequence = 0;
  const queue = createCheckpointQueue(
    api,
    () => {},
    () => String(++sequence).padStart(32, '0'),
  );
  return { api, queue };
}
beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

it('debounces edits and reports saved only after acknowledgment', async () => {
  const { api, queue } = setup();
  queue.edit('key', context, draft('1'));
  queue.edit('key', context, draft('2'));
  expect(api.save).not.toHaveBeenCalled();
  expect(queue.hasPending()).toBe(true);
  await vi.advanceTimersByTimeAsync(600);
  expect(api.save).toHaveBeenCalledTimes(1);
  expect(api.save.mock.calls[0][2].draft).toEqual(draft('2'));
  expect(queue.get('key').status).toBe('saved');
});

it('serializes newer input after an in-flight save', async () => {
  const { api, queue } = setup();
  let finish;
  api.save.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  queue.edit('key', context, draft('1'));
  const saving = queue.flush('key');
  queue.edit('key', context, draft('2'));
  expect(api.save).toHaveBeenCalledTimes(1);
  finish({ draftRevision: 1 });
  await saving;
  expect(api.save).toHaveBeenCalledTimes(2);
  expect(api.save.mock.calls[1][2]).toMatchObject({ expectedDraftRevision: 1, draft: draft('2') });
  queue.stop();
});

it('retries a failed operation unchanged before sending newer edits', async () => {
  const { api, queue } = setup();
  api.save.mockRejectedValueOnce(new Error('response lost'));
  queue.edit('key', context, draft('1'));
  await expect(queue.flush('key')).rejects.toThrow('response lost');
  queue.edit('key', context, draft('2'));
  await queue.retry('key');
  expect(api.save.mock.calls[1][2]).toEqual(api.save.mock.calls[0][2]);
  expect(api.save.mock.calls[2][2].draft).toEqual(draft('2'));
  expect(queue.get('key').status).toBe('saved');
});

it('flushes before retirement and preserves failed retirement identity', async () => {
  const { api, queue } = setup();
  api.retire.mockRejectedValueOnce(new Error('offline'));
  queue.edit('key', context, draft('1'));
  await expect(queue.retire('key', 'approved')).rejects.toThrow('offline');
  expect(() => queue.edit('key', context, draft('2'))).toThrow('đóng');
  await queue.retry('key');
  expect(api.retire.mock.calls[0]).toEqual(api.retire.mock.calls[1]);
  expect(api.retire.mock.calls[0][2]).toMatchObject({
    expectedDraftRevision: 1,
    reason: 'approved',
  });
  expect(queue.get('key')).toBeUndefined();
});

it('restores the original revision without auto-approving or writing', () => {
  const { api, queue } = setup();
  queue.adopt('key', {
    ...context,
    draftId: 'old',
    sessionId: 'previous',
    draftRevision: 4,
    draft: draft('1'),
  });
  expect(api.save).not.toHaveBeenCalled();
  expect(queue.get('key')).toMatchObject({ baseRevision: 12, revision: 4, saved: draft('1') });
  expect(() => queue.adopt('key', {})).toThrow();
});

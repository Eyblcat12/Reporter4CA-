import { editorDraftApi, getTemplateWorkspace } from './templateStudioApi';

afterEach(() => vi.unstubAllGlobals());

it('bounds checkpoint requests and reports an uncertain outcome on timeout', async () => {
  vi.useFakeTimers();
  vi.stubGlobal(
    'fetch',
    vi.fn(
      (_url, options) =>
        new Promise((_resolve, reject) => {
          options.signal.addEventListener('abort', () =>
            reject(new DOMException('Timed out', 'AbortError')),
          );
        }),
    ),
  );
  try {
    const result = editorDraftApi
      .save('workspace', 'draft', { operationId: 'same-id' })
      .catch((error) => error);
    await vi.advanceTimersByTimeAsync(15000);
    expect(await result).toMatchObject({
      retryable: true,
      message: expect.stringContaining('kết quả chưa xác định'),
    });
  } finally {
    vi.useRealTimers();
  }
});

it('preserves cancellation instead of reporting a backend outage', async () => {
  const error = new DOMException('Cancelled', 'AbortError');
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(error));
  await expect(getTemplateWorkspace('a')).rejects.toBe(error);
});

it('does not misdiagnose a missing resource as a disabled subsystem', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({}) }),
  );
  await expect(getTemplateWorkspace('missing')).rejects.toMatchObject({
    status: 404,
    message: expect.stringContaining('Không tìm thấy tài nguyên'),
  });
});

it('retains server conflict details and marks the error as a conflict', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ detail: 'Revision changed' }),
    }),
  );
  await expect(getTemplateWorkspace('a')).rejects.toMatchObject({
    conflict: true,
    message: 'Revision changed',
  });
});

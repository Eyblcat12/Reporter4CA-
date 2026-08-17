import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ReporterProvider, useReporter } from './useReporter';

const wrapper = ({ children }) => <ReporterProvider>{children}</ReporterProvider>;
const jsonResponse = (payload, ok = true) => ({
  ok,
  status: ok ? 200 : 400,
  json: vi.fn().mockResolvedValue(payload),
});
const statusResponse = (status, payload = {}) => ({
  ok: status >= 200 && status < 300,
  status,
  json: vi.fn().mockResolvedValue(payload),
  blob: vi.fn().mockResolvedValue(new Blob(['docx'])),
});

beforeEach(() => {
  global.fetch = vi.fn();
  URL.createObjectURL = vi.fn(() => 'blob:test');
  URL.revokeObjectURL = vi.fn();
  HTMLAnchorElement.prototype.click = vi.fn();
});

describe('ReporterProvider API workflow', () => {
  it('opens Configure with a rule draft sourced from an imported note', async () => {
    fetch.mockResolvedValueOnce(
      jsonResponse({
        rows: [{ type: 'client', hostname: 'pc-note', notes: 'Acme Relay detected' }],
        payload: {},
      }),
    );
    const { result } = renderHook(() => useReporter(), { wrapper });
    await act(() => result.current.loadSample());
    act(() => result.current.startRuleFromRow(0, 'notes'));
    expect(result.current.currentStep).toBe(2);
    expect(result.current.ruleDraftSource).toEqual(
      expect.objectContaining({
        row: 0,
        field: 'notes',
        value: 'Acme Relay detected',
        hostname: 'pc-note',
      }),
    );
  });

  it('imports a file with suggested column mapping', async () => {
    fetch
      .mockResolvedValueOnce(
        jsonResponse({
          columns: ['Host', 'IP'],
          suggestedMapping: { Host: 'hostname', IP: 'ip' },
          sheets: [],
          headerRow: 0,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          rows: [{ type: 'server', hostname: 'srv-01', ip: '10.0.0.1' }],
          counts: { servers: 1, clients: 0, total: 1 },
          payload: {},
          previewText: 'ok',
        }),
      );
    const { result } = renderHook(() => useReporter(), { wrapper });
    await act(() => result.current.importFile('assets.csv', 'data:text/csv;base64,QQ==', 10));
    expect(result.current.columnMapping).toEqual({ Host: 'hostname', IP: 'ip' });
    expect(result.current.rows[0].hostname).toBe('srv-01');
    expect(result.current.importProgress).toEqual(
      expect.objectContaining({
        status: 'completed',
        phase: 'completed',
        progress: 100,
        rowCount: 1,
      }),
    );
    expect(fetch.mock.calls[1][0]).toBe('/api/import-file');
  });

  it('blocks download when validation reports a severe error', async () => {
    fetch
      .mockResolvedValueOnce(
        jsonResponse({ rows: [{ type: 'server', hostname: '' }], payload: {} }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          valid: false,
          issues: [{ row: 1, level: 'error' }],
          summary: { errorRows: 1 },
        }),
      );
    const { result } = renderHook(() => useReporter(), { wrapper });
    await act(() => result.current.loadSample());
    await expect(act(() => result.current.generateReport())).rejects.toThrow(/lỗi nghiêm trọng/i);
    expect(fetch.mock.calls.some(([url]) => url === '/api/generate')).toBe(false);
  });

  it('validates, generates and downloads a report', async () => {
    fetch
      .mockResolvedValueOnce(
        jsonResponse({ rows: [{ type: 'server', hostname: 'srv-01' }], payload: {} }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ valid: true, issues: [], summary: { totalRows: 1, validRows: 1 } }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          job: { id: 'job-1', status: 'queued', phase: 'queued', progress: 0 },
          deduplicated: false,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          job: {
            id: 'job-1',
            status: 'completed',
            phase: 'completed',
            progress: 100,
            filename: 'assessment.docx',
            reportId: 'report-1',
          },
        }),
      )
      .mockResolvedValueOnce(
        new Response(new Blob(['docx']), {
          status: 200,
        }),
      );
    const { result } = renderHook(() => useReporter(), { wrapper });
    await act(() => result.current.loadSample());
    await act(() => result.current.generateReport());
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalled();
    expect(result.current.lastReportId).toBe('report-1');
    const generateCall = fetch.mock.calls.find(([url]) => url === '/api/report-jobs');
    expect(JSON.parse(generateCall[1].body).metadata.dataQuality.totalRows).toBe(1);
    expect(fetch).toHaveBeenCalledWith('/api/report-jobs/job-1/download');
  });

  it('saves presets and updates templates through their API contracts', async () => {
    fetch
      .mockResolvedValueOnce(jsonResponse({ id: 'preset-1', ok: true }))
      .mockResolvedValueOnce(jsonResponse({ presets: [{ id: 'preset-1', name: 'Team' }] }))
      .mockResolvedValueOnce(jsonResponse({ ok: true }))
      .mockResolvedValueOnce(jsonResponse({ templates: [] }));
    const { result } = renderHook(() => useReporter(), { wrapper });
    await act(() => result.current.savePreset('Team'));
    await act(() => result.current.updateTemplate('tpl-1', { name: 'Technical' }));
    expect(fetch).toHaveBeenCalledWith('/api/presets', expect.objectContaining({ method: 'POST' }));
    expect(fetch).toHaveBeenCalledWith(
      '/api/templates/tpl-1',
      expect.objectContaining({ method: 'PATCH' }),
    );
  });

  it('surfaces a failed background job without attempting a download', async () => {
    fetch
      .mockResolvedValueOnce(
        jsonResponse({ rows: [{ type: 'client', hostname: 'pc-01' }], payload: {} }),
      )
      .mockResolvedValueOnce(jsonResponse({ valid: true, issues: [], summary: { totalRows: 1 } }))
      .mockResolvedValueOnce(
        jsonResponse({ job: { id: 'job-fail', status: 'queued' }, deduplicated: false }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          job: {
            id: 'job-fail',
            status: 'failed',
            phase: 'failed',
            errorMessage: 'Generation failed safely',
          },
        }),
      );
    const { result } = renderHook(() => useReporter(), { wrapper });
    await act(() => result.current.loadSample());
    let failure;
    await act(async () => {
      try {
        await result.current.generateReport();
      } catch (error) {
        failure = error;
      }
    });
    expect(failure.message).toBe('Generation failed safely');
    await waitFor(() => expect(result.current.activeReportJob?.status).toBe('failed'));
    expect(fetch.mock.calls.some(([url]) => String(url).endsWith('/download'))).toBe(false);
  });

  it('keeps imported state usable when the backend becomes unavailable', async () => {
    fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    const { result } = renderHook(() => useReporter(), { wrapper });
    await act(() => result.current.importFile('offline.csv', 'data:text/csv;base64,QQ==', 10));
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toMatch(/Failed to fetch/);
    expect(result.current.importProgress).toEqual(
      expect.objectContaining({ status: 'failed', phase: 'failed', progress: 24 }),
    );
    expect(result.current.rows).toEqual([]);
  });

  it('sends disabled rule ids with the queued report request', async () => {
    fetch
      .mockResolvedValueOnce(
        jsonResponse({ rows: [{ type: 'client', hostname: 'pc-01' }], payload: {} }),
      )
      .mockResolvedValueOnce(jsonResponse({ valid: true, issues: [], summary: { totalRows: 1 } }))
      .mockResolvedValueOnce(
        jsonResponse({ job: { id: 'job-rule', status: 'queued' }, deduplicated: false }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ job: { id: 'job-rule', status: 'cancelled', phase: 'cancelled' } }),
      );
    const { result } = renderHook(() => useReporter(), { wrapper });
    await act(() => result.current.loadSample());
    act(() =>
      result.current.setReportSettings({
        ...result.current.reportSettings,
        ruleSettings: { disabledRuleIds: ['PROXY_TOOL_REVIEW'] },
      }),
    );
    await act(() => result.current.generateReport());
    const request = fetch.mock.calls.find(([url]) => url === '/api/report-jobs');
    expect(JSON.parse(request[1].body).metadata.ruleSettings.disabledRuleIds).toEqual([
      'PROXY_TOOL_REVIEW',
    ]);
  });

  it('keeps existing rows after a 422 import and clears the error after a successful retry', async () => {
    fetch
      .mockResolvedValueOnce(
        jsonResponse({ rows: [{ type: 'server', hostname: 'srv-existing' }], payload: {} }),
      )
      .mockResolvedValueOnce(statusResponse(422, { detail: 'Header row is invalid' }))
      .mockResolvedValueOnce(
        jsonResponse({
          columns: ['Host'],
          suggestedMapping: { Host: 'hostname' },
          sheets: [],
          headerRow: 0,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          rows: [{ type: 'client', hostname: 'pc-recovered' }],
          counts: { servers: 0, clients: 1, total: 1 },
          payload: {},
          previewText: 'recovered',
        }),
      );
    const { result } = renderHook(() => useReporter(), { wrapper });
    await act(() => result.current.loadSample());
    await act(() => result.current.importFile('invalid.csv', 'data:text/csv;base64,QQ==', 10));
    expect(result.current.error).toBe('Header row is invalid');
    expect(result.current.rows[0].hostname).toBe('srv-existing');

    await act(() => result.current.importFile('fixed.csv', 'data:text/csv;base64,Qg==', 10));
    expect(result.current.error).toBeNull();
    expect(result.current.rows[0].hostname).toBe('pc-recovered');
  });

  it('recovers preview state after a server error without losing imported rows', async () => {
    fetch
      .mockResolvedValueOnce(
        jsonResponse({ rows: [{ type: 'client', hostname: 'pc-preview' }], payload: {} }),
      )
      .mockResolvedValueOnce(statusResponse(500))
      .mockResolvedValueOnce(statusResponse(404))
      .mockResolvedValueOnce(statusResponse(200));
    const { result } = renderHook(() => useReporter(), { wrapper });
    await act(() => result.current.loadSample());
    await act(() => result.current.previewDocx());
    expect(result.current.error).toBe('Preview error: 500');
    expect(result.current.rows[0].hostname).toBe('pc-preview');

    await act(() => result.current.previewDocx());
    expect(result.current.error).toBeNull();
    expect(result.current.showPreview).toBe(true);
    expect(result.current.rows[0].hostname).toBe('pc-preview');
  });

  it('marks an asynchronous Preview current and sends it for explicit promotion', async () => {
    fetch
      .mockResolvedValueOnce(
        jsonResponse({ rows: [{ type: 'server', hostname: 'srv-preview-job' }], payload: {} }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          previewId: 'preview-1',
          jobId: 'preview-job-1',
          status: 'ready',
          signature: 'signature-1',
          progress: 100,
          phase: 'completed',
          cacheMode: 'deterministic',
        }),
      )
      .mockResolvedValueOnce(statusResponse(200))
      .mockResolvedValueOnce(jsonResponse({ valid: true, issues: [], summary: { totalRows: 1 } }))
      .mockResolvedValueOnce(
        jsonResponse({
          job: { id: 'report-from-preview', status: 'cancelled' },
          deduplicated: false,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          job: { id: 'report-from-preview', status: 'cancelled', phase: 'cancelled' },
        }),
      );
    const { result } = renderHook(() => useReporter(), { wrapper });
    await act(() => result.current.loadSample());
    await act(() => result.current.previewDocx());
    expect(result.current.previewState.status).toBe('current');
    expect(result.current.previewState.previewId).toBe('preview-1');

    await act(() => result.current.generateReport());
    const queued = fetch.mock.calls.find(([url]) => url === '/api/report-jobs');
    expect(JSON.parse(queued[1].body).previewId).toBe('preview-1');
  });

  it('marks a completed Preview stale when report settings changed during generation', async () => {
    let resolveContent;
    const contentPromise = new Promise((resolve) => {
      resolveContent = resolve;
    });
    fetch
      .mockResolvedValueOnce(
        jsonResponse({ rows: [{ type: 'client', hostname: 'pc-race' }], payload: {} }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          previewId: 'preview-race',
          jobId: 'job-race',
          status: 'ready',
          signature: 'signature-race',
          progress: 100,
          phase: 'completed',
          cacheMode: 'deterministic',
        }),
      )
      .mockReturnValueOnce(contentPromise);
    const { result } = renderHook(() => useReporter(), { wrapper });
    await act(() => result.current.loadSample());
    let pending;
    act(() => {
      pending = result.current.previewDocx();
    });
    await waitFor(() =>
      expect(fetch.mock.calls.some(([url]) => String(url).endsWith('/content'))).toBe(true),
    );
    act(() =>
      result.current.setReportSettings({
        ...result.current.reportSettings,
        organization: 'Changed while Preview was running',
      }),
    );
    resolveContent(statusResponse(200));
    await act(() => pending);
    expect(result.current.previewState.status).toBe('stale');
  });

  it('cancels a Preview only through the explicit DELETE action', async () => {
    fetch
      .mockResolvedValueOnce(
        jsonResponse({ rows: [{ type: 'client', hostname: 'pc-cancel-preview' }], payload: {} }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          previewId: 'preview-cancel',
          jobId: 'job-preview-cancel',
          status: 'ready',
          signature: 'signature-cancel',
          progress: 100,
          phase: 'completed',
          cacheMode: 'deterministic',
        }),
      )
      .mockResolvedValueOnce(statusResponse(200))
      .mockResolvedValueOnce(jsonResponse({ status: 'cancelled' }));
    const { result } = renderHook(() => useReporter(), { wrapper });
    await act(() => result.current.loadSample());
    await act(() => result.current.previewDocx());
    await act(() => result.current.cancelPreview());
    expect(fetch).toHaveBeenCalledWith('/api/preview-jobs/preview-cancel', { method: 'DELETE' });
    expect(result.current.previewState.errorCode).toBe('CANCELLED');
  });

  it('allows retry after a 429 queue response and does not duplicate the failed request', async () => {
    fetch
      .mockResolvedValueOnce(
        jsonResponse({ rows: [{ type: 'server', hostname: 'srv-busy' }], payload: {} }),
      )
      .mockResolvedValueOnce(jsonResponse({ valid: true, issues: [], summary: { totalRows: 1 } }))
      .mockResolvedValueOnce(statusResponse(429, { detail: 'Job queue is full' }))
      .mockResolvedValueOnce(jsonResponse({ valid: true, issues: [], summary: { totalRows: 1 } }))
      .mockResolvedValueOnce(
        jsonResponse({ job: { id: 'job-retry', status: 'queued' }, deduplicated: false }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ job: { id: 'job-retry', status: 'cancelled', phase: 'cancelled' } }),
      );
    const { result } = renderHook(() => useReporter(), { wrapper });
    await act(() => result.current.loadSample());
    await expect(act(() => result.current.generateReport())).rejects.toThrow('Job queue is full');
    expect(fetch.mock.calls.filter(([url]) => url === '/api/report-jobs')).toHaveLength(1);

    await act(() => result.current.generateReport());
    expect(result.current.error).toBeNull();
    expect(fetch.mock.calls.filter(([url]) => url === '/api/report-jobs')).toHaveLength(2);
    expect(result.current.rows[0].hostname).toBe('srv-busy');
  });

  it('retries transient job polling failures and completes the original job', async () => {
    const timeout = vi.spyOn(window, 'setTimeout').mockImplementation((callback) => {
      callback();
      return 1;
    });
    try {
      fetch
        .mockResolvedValueOnce(
          jsonResponse({ rows: [{ type: 'server', hostname: 'srv-poll' }], payload: {} }),
        )
        .mockResolvedValueOnce(jsonResponse({ valid: true, issues: [], summary: { totalRows: 1 } }))
        .mockResolvedValueOnce(
          jsonResponse({ job: { id: 'job-poll', status: 'queued' }, deduplicated: false }),
        )
        .mockRejectedValueOnce(new TypeError('Network interrupted'))
        .mockResolvedValueOnce(statusResponse(503))
        .mockResolvedValueOnce(
          jsonResponse({
            job: {
              id: 'job-poll',
              status: 'completed',
              filename: 'poll.docx',
              reportId: 'report-poll',
            },
          }),
        )
        .mockResolvedValueOnce(statusResponse(200));
      const { result } = renderHook(() => useReporter(), { wrapper });
      await act(() => result.current.loadSample());
      await act(() => result.current.generateReport());
      expect(result.current.lastReportId).toBe('report-poll');
      expect(result.current.error).toBeNull();
      expect(result.current.logs.filter((line) => line.includes('đang thử lại'))).toHaveLength(2);
    } finally {
      timeout.mockRestore();
    }
  });

  it('releases an unavailable job after retry exhaustion so the user can generate again', async () => {
    const timeout = vi.spyOn(window, 'setTimeout').mockImplementation((callback) => {
      callback();
      return 1;
    });
    try {
      fetch
        .mockResolvedValueOnce(
          jsonResponse({ rows: [{ type: 'client', hostname: 'pc-retry' }], payload: {} }),
        )
        .mockResolvedValueOnce(jsonResponse({ valid: true, issues: [], summary: { totalRows: 1 } }))
        .mockResolvedValueOnce(
          jsonResponse({ job: { id: 'job-lost', status: 'queued' }, deduplicated: false }),
        )
        .mockRejectedValueOnce(new TypeError('Offline 1'))
        .mockRejectedValueOnce(new TypeError('Offline 2'))
        .mockRejectedValueOnce(new TypeError('Offline 3'))
        .mockRejectedValueOnce(new TypeError('Offline 4'))
        .mockResolvedValueOnce(jsonResponse({ valid: true, issues: [], summary: { totalRows: 1 } }))
        .mockResolvedValueOnce(
          jsonResponse({ job: { id: 'job-new', status: 'queued' }, deduplicated: false }),
        )
        .mockResolvedValueOnce(
          jsonResponse({ job: { id: 'job-new', status: 'cancelled', phase: 'cancelled' } }),
        );
      const { result } = renderHook(() => useReporter(), { wrapper });
      await act(() => result.current.loadSample());
      let failure;
      await act(async () => {
        try {
          await result.current.generateReport();
        } catch (error) {
          failure = error;
        }
      });
      expect(failure.message).toMatch(/sau 3 lần thử lại/i);
      expect(result.current.activeReportJob?.status).toBe('unavailable');
      expect(result.current.rows[0].hostname).toBe('pc-retry');

      await act(() => result.current.generateReport());
      expect(result.current.activeReportJob?.id).toBe('job-new');
      expect(result.current.error).toBeNull();
      expect(fetch.mock.calls.filter(([url]) => url === '/api/report-jobs')).toHaveLength(2);
    } finally {
      timeout.mockRestore();
    }
  });
});

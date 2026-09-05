import {
  applyTemplateWorkspaceRetention,
  analyzeTemplateSource,
  approveTemplateMapping,
  approveTemplateValidationBaseline,
  cloneTemplateWorkspace,
  createTemplateWorkspace,
  createTemplateValidationRun,
  downloadTemplateValidationArtifact,
  getTemplatePackCatalog,
  listAllTemplateWorkspaces,
  listTemplateWorkspaces,
  listTemplateValidationRuns,
  previewTemplateWorkspaceRetention,
  previewTemplatePackCatalogRecovery,
  recoverTemplatePackCatalog,
  renameTemplateWorkspace,
  restoreTemplateWorkspaceRetention,
  publishTemplateValidationRun,
  setTemplateWorkspaceArchived,
  selectTemplatePackVersion,
  TemplateStudioApiError,
} from './templateStudioApi';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('Template Studio API client', () => {
  it('classifies a revision conflict and preserves the backend detail', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: vi.fn().mockResolvedValue({ detail: 'Expected revision 12, found 13.' }),
      }),
    );

    await expect(listTemplateWorkspaces()).rejects.toMatchObject({
      name: 'TemplateStudioApiError',
      message: 'Expected revision 12, found 13.',
      status: 409,
      conflict: true,
      retryable: true,
    });
  });

  it('classifies a network failure as retryable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network down')));

    await expect(listTemplateWorkspaces()).rejects.toEqual(
      expect.objectContaining({
        name: 'TemplateStudioApiError',
        retryable: true,
        conflict: false,
      }),
    );
  });

  it('sends the optimistic revision mapping contract without changing the payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ workspaceId: 'workspace-1', revision: 13 }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const payload = {
      anchor: { kind: 'token', value: '{{REPORT_TITLE}}' },
      fields: [],
      expectedRevision: 12,
    };

    await approveTemplateMapping('workspace-1', 'report.title', payload);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/template-packs/workspaces/workspace-1/mappings/report.title',
      expect.objectContaining({ method: 'PUT', body: JSON.stringify(payload) }),
    );
  });

  it('keeps template analysis separate from workspace creation', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({}),
    });
    vi.stubGlobal('fetch', fetchMock);
    const analysisPayload = {
      filename: 'customer.docx',
      contentBase64: 'UEs=',
      reportType: 'full',
    };
    const createPayload = {
      ...analysisPayload,
      profileId: 'customer-full',
      displayName: 'Customer Full',
      version: '0.1.0',
    };

    await analyzeTemplateSource(analysisPayload);
    await createTemplateWorkspace(createPayload);

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/template-packs/analyze-template',
      '/api/template-packs/workspaces',
    ]);
    expect(fetchMock.mock.calls[0][1].body).toBe(JSON.stringify(analysisPayload));
    expect(fetchMock.mock.calls[1][1].body).toBe(JSON.stringify(createPayload));
  });

  it('uses a stable error type for disabled backend responses', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: vi.fn().mockResolvedValue({ detail: 'Template Pack API is not enabled.' }),
      }),
    );

    await expect(listTemplateWorkspaces()).rejects.toBeInstanceOf(TemplateStudioApiError);
  });

  it('builds bounded workspace list filters', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ items: [] }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await listTemplateWorkspaces({ archived: true, q: '  incident team  ' });

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/template-packs/workspaces?archived=true&limit=100&q=incident+team',
      expect.any(Object),
    );
  });

  it('sends revision guards for lifecycle mutations', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ workspaceId: 'workspace-1', revision: 13 }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await renameTemplateWorkspace('workspace-1', 'Renamed', 12);
    await cloneTemplateWorkspace('workspace-1', {
      displayName: 'Copy',
      profileId: 'copy-profile',
      version: '0.2.0',
      expectedRevision: 12,
    });
    await setTemplateWorkspaceArchived('workspace-1', true, 12);

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/template-packs/workspaces/workspace-1/rename',
      '/api/template-packs/workspaces/workspace-1/clone',
      '/api/template-packs/workspaces/workspace-1/archive',
    ]);
    expect(fetchMock.mock.calls[2][1].body).toBe(
      JSON.stringify({ archived: true, expectedRevision: 12 }),
    );
  });

  it('loads every stable workspace page instead of silently truncating the list', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue({
          items: [{ workspaceId: 'one' }],
          hasMore: true,
          nextCursor: 'cursor-2',
          skippedCorrupt: 1,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue({
          items: [{ workspaceId: 'two' }],
          hasMore: false,
          nextCursor: null,
          skippedCorrupt: 1,
        }),
      });
    vi.stubGlobal('fetch', fetchMock);

    await expect(listAllTemplateWorkspaces()).resolves.toEqual({
      items: [{ workspaceId: 'one' }, { workspaceId: 'two' }],
      skippedCorrupt: 1,
    });
    expect(fetchMock.mock.calls[1][0]).toContain('cursor=cursor-2');
  });

  it('keeps retention as preview, confirmed quarantine, and explicit restore', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({}),
    });
    vi.stubGlobal('fetch', fetchMock);

    await previewTemplateWorkspaceRetention(120);
    await applyTemplateWorkspaceRetention('a'.repeat(64));
    await restoreTemplateWorkspaceRetention('0123456789abcdef');

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/template-packs/workspaces/retention/preview?retentionDays=120',
      '/api/template-packs/workspaces/retention/apply',
      '/api/template-packs/workspaces/retention/0123456789abcdef/restore',
    ]);
    expect(fetchMock.mock.calls[1][1]).toEqual(
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ confirmationToken: 'a'.repeat(64) }),
      }),
    );
    expect(fetchMock.mock.calls[2][1]).toEqual(expect.objectContaining({ method: 'POST' }));
  });

  it('keeps catalog recovery behind a preview token', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({}),
    });
    vi.stubGlobal('fetch', fetchMock);

    await getTemplatePackCatalog();
    await previewTemplatePackCatalogRecovery();
    await recoverTemplatePackCatalog('c'.repeat(64));

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/template-packs/catalog',
      '/api/template-packs/catalog/recovery',
      '/api/template-packs/catalog/recovery',
    ]);
    expect(fetchMock.mock.calls[2][1]).toEqual(
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ confirmationToken: 'c'.repeat(64) }),
      }),
    );
  });

  it('sends the complete two-pass validation contract', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({}),
    });
    vi.stubGlobal('fetch', fetchMock);
    const baselinePayload = {
      rows: [{ hostname: 'PC-01' }],
      fixtureId: 'pilot-v1',
      expectedWorkspaceRevision: 12,
      baselineRunId: '',
    };
    const approval = {
      expectedWorkspaceRevision: 12,
      reviewer: 'reviewer@example.test',
      artifactSha256: 'a'.repeat(64),
    };

    await listTemplateValidationRuns('workspace-1');
    await createTemplateValidationRun('workspace-1', baselinePayload);
    await approveTemplateValidationBaseline('workspace-1', 'b'.repeat(64), approval);
    await publishTemplateValidationRun('workspace-1', 'c'.repeat(64), {
      ...approval,
      expectedCatalogRevision: 4,
    });

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/template-packs/workspaces/workspace-1/validation-runs?limit=100',
      '/api/template-packs/workspaces/workspace-1/validation-runs',
      `/api/template-packs/workspaces/workspace-1/validation-runs/${'b'.repeat(64)}/approve-baseline`,
      `/api/template-packs/workspaces/workspace-1/validation-runs/${'c'.repeat(64)}/publish`,
    ]);
    expect(fetchMock.mock.calls[1][1].body).toBe(JSON.stringify(baselinePayload));
    expect(fetchMock.mock.calls[3][1].body).toBe(
      JSON.stringify({ ...approval, expectedCatalogRevision: 4 }),
    );
  });

  it('downloads a checksum-bound validation artifact without JSON parsing', async () => {
    const blob = new Blob(['docx']);
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: {
        get: vi.fn((name) =>
          name === 'Content-Disposition'
            ? 'attachment; filename="validation-run.docx"'
            : name === 'X-Artifact-SHA256'
              ? 'd'.repeat(64)
              : '',
        ),
      },
      blob: vi.fn().mockResolvedValue(blob),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      downloadTemplateValidationArtifact('workspace-1', 'e'.repeat(64)),
    ).resolves.toEqual({
      blob,
      filename: 'validation-run.docx',
      artifactSha256: 'd'.repeat(64),
    });
  });

  it('uses revision guards for isolated catalog activation and rollback', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({}),
    });
    vi.stubGlobal('fetch', fetchMock);

    await selectTemplatePackVersion('customer-summary', '2.0.0', 5, 'activate');
    await selectTemplatePackVersion('customer-summary', '1.0.0', 6, 'rollback');

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/template-packs/catalog/customer-summary/activate',
      '/api/template-packs/catalog/customer-summary/rollback',
    ]);
    expect(fetchMock.mock.calls[0][1].body).toBe(
      JSON.stringify({ version: '2.0.0', expectedRevision: 5 }),
    );
    expect(fetchMock.mock.calls[1][1].body).toBe(
      JSON.stringify({ version: '1.0.0', expectedRevision: 6 }),
    );
  });
});

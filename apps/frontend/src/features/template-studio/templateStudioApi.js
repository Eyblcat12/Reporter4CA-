const API_ROOT = '/api/template-packs';

export class TemplateStudioApiError extends Error {
  constructor(message, { status = 0, retryable = false, conflict = false } = {}) {
    super(message);
    this.name = 'TemplateStudioApiError';
    this.status = status;
    this.retryable = retryable;
    this.conflict = conflict;
  }
}

async function requestResponse(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
  } catch (_error) {
    throw new TemplateStudioApiError('Không thể kết nối với backend Template Studio.', {
      retryable: true,
    });
  }

  if (!response.ok) {
    let detail;
    try {
      const payload = await response.json();
      detail = typeof payload.detail === 'string' ? payload.detail : '';
    } catch (_error) {
      detail = '';
    }
    const conflict = response.status === 409;
    const disabled = response.status === 404;
    throw new TemplateStudioApiError(
      detail ||
        (conflict
          ? 'Workspace đã có revision mới.'
          : disabled
            ? 'Template Studio chưa được bật ở backend.'
            : 'Yêu cầu Template Studio không thành công.'),
      {
        status: response.status,
        retryable: conflict || response.status >= 500,
        conflict,
      },
    );
  }
  return response;
}

async function request(path, options = {}) {
  return (await requestResponse(path, options)).json();
}

export async function listTemplateWorkspaces({
  signal,
  archived = false,
  q = '',
  cursor = '',
} = {}) {
  const params = new URLSearchParams({
    archived: String(archived),
    limit: '100',
  });
  if (q.trim()) params.set('q', q.trim());
  if (cursor) params.set('cursor', cursor);
  return request(`/workspaces?${params}`, { signal });
}

export async function listAllTemplateWorkspaces({ signal, archived = false } = {}) {
  const items = [];
  const cursors = new Set();
  let cursor = '';
  let skippedCorrupt = 0;
  do {
    const page = await listTemplateWorkspaces({ signal, archived, cursor });
    items.push(...(page.items || []));
    skippedCorrupt = Math.max(skippedCorrupt, page.skippedCorrupt || 0);
    if (!page.hasMore) break;
    if (!page.nextCursor || cursors.has(page.nextCursor)) {
      throw new TemplateStudioApiError('Phân trang workspace không ổn định. Hãy tải lại.', {
        retryable: true,
      });
    }
    cursors.add(page.nextCursor);
    cursor = page.nextCursor;
  } while (cursor);
  return { items, skippedCorrupt };
}

export async function getTemplateWorkspace(workspaceId, { signal } = {}) {
  return request(`/workspaces/${encodeURIComponent(workspaceId)}`, { signal });
}

export async function analyzeTemplateSource(payload) {
  return request('/analyze-template', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createTemplateWorkspace(payload) {
  return request('/workspaces', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function approveTemplateMapping(workspaceId, semantic, payload) {
  return request(
    `/workspaces/${encodeURIComponent(workspaceId)}/mappings/${encodeURIComponent(semantic)}`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
  );
}

export async function removeTemplateMapping(workspaceId, semantic, expectedRevision) {
  return request(
    `/workspaces/${encodeURIComponent(workspaceId)}/mappings/${encodeURIComponent(semantic)}/remove`,
    {
      method: 'POST',
      body: JSON.stringify({ expectedRevision }),
    },
  );
}

export async function renameTemplateWorkspace(workspaceId, displayName, expectedRevision) {
  return request(`/workspaces/${encodeURIComponent(workspaceId)}/rename`, {
    method: 'PATCH',
    body: JSON.stringify({ displayName, expectedRevision }),
  });
}

export async function cloneTemplateWorkspace(workspaceId, payload) {
  return request(`/workspaces/${encodeURIComponent(workspaceId)}/clone`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function setTemplateWorkspaceArchived(workspaceId, archived, expectedRevision) {
  return request(`/workspaces/${encodeURIComponent(workspaceId)}/archive`, {
    method: 'POST',
    body: JSON.stringify({ archived, expectedRevision }),
  });
}

export async function exportTemplateWorkspace(workspaceId) {
  return request(`/workspaces/${encodeURIComponent(workspaceId)}/export`);
}

export async function importTemplateWorkspace(filename, contentBase64) {
  return request('/workspaces/import', {
    method: 'POST',
    body: JSON.stringify({ filename, contentBase64 }),
  });
}

export async function previewTemplateWorkspaceRetention(retentionDays = 90) {
  const params = new URLSearchParams({ retentionDays: String(retentionDays) });
  return request(`/workspaces/retention/preview?${params}`);
}

export async function applyTemplateWorkspaceRetention(confirmationToken) {
  return request('/workspaces/retention/apply', {
    method: 'POST',
    body: JSON.stringify({ confirmationToken }),
  });
}

export async function restoreTemplateWorkspaceRetention(quarantineId) {
  return request(`/workspaces/retention/${encodeURIComponent(quarantineId)}/restore`, {
    method: 'POST',
  });
}

export async function getTemplatePackCatalog() {
  return request('/catalog');
}

export async function previewTemplatePackCatalogRecovery() {
  return request('/catalog/recovery');
}

export async function recoverTemplatePackCatalog(confirmationToken) {
  return request('/catalog/recovery', {
    method: 'POST',
    body: JSON.stringify({ confirmationToken }),
  });
}

export async function selectTemplatePackVersion(packId, version, expectedRevision, action) {
  if (action !== 'activate' && action !== 'rollback') {
    throw new TemplateStudioApiError('Thao tác chọn version không hợp lệ.');
  }
  return request(`/catalog/${encodeURIComponent(packId)}/${action}`, {
    method: 'POST',
    body: JSON.stringify({ version, expectedRevision }),
  });
}

export async function listTemplateValidationRuns(workspaceId) {
  return request(`/workspaces/${encodeURIComponent(workspaceId)}/validation-runs?limit=100`);
}

export async function createTemplateValidationRun(workspaceId, payload) {
  return request(`/workspaces/${encodeURIComponent(workspaceId)}/validation-runs`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function downloadTemplateValidationArtifact(workspaceId, runId) {
  const response = await requestResponse(
    `/workspaces/${encodeURIComponent(workspaceId)}/validation-runs/${encodeURIComponent(runId)}/artifact`,
  );
  const disposition = response.headers?.get?.('Content-Disposition') || '';
  const filename =
    /filename="([^"]+)"/i.exec(disposition)?.[1] || `validation-${runId.slice(0, 12)}.docx`;
  return {
    blob: await response.blob(),
    filename,
    artifactSha256: response.headers?.get?.('X-Artifact-SHA256') || '',
  };
}

export async function approveTemplateValidationBaseline(workspaceId, runId, payload) {
  return request(
    `/workspaces/${encodeURIComponent(workspaceId)}/validation-runs/${encodeURIComponent(runId)}/approve-baseline`,
    { method: 'POST', body: JSON.stringify(payload) },
  );
}

export async function publishTemplateValidationRun(workspaceId, runId, payload) {
  return request(
    `/workspaces/${encodeURIComponent(workspaceId)}/validation-runs/${encodeURIComponent(runId)}/publish`,
    { method: 'POST', body: JSON.stringify(payload) },
  );
}

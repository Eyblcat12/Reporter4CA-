import { useCallback, useEffect, useState } from 'react';
import TemplateStudioWorkbench from './TemplateStudioWorkbench';
import {
  applyTemplateWorkspaceRetention,
  approveTemplateMapping,
  approveTemplateValidationBaseline,
  analyzeTemplateSource,
  cloneTemplateWorkspace,
  createTemplateWorkspace,
  createTemplateValidationRun,
  downloadTemplateValidationArtifact,
  exportTemplateWorkspace,
  getTemplatePackCatalog,
  getTemplateWorkspace,
  importTemplateWorkspace,
  listAllTemplateWorkspaces,
  listTemplateValidationRuns,
  removeTemplateMapping,
  renameTemplateWorkspace,
  previewTemplateWorkspaceRetention,
  previewTemplatePackCatalogRecovery,
  publishTemplateValidationRun,
  recoverTemplatePackCatalog,
  restoreTemplateWorkspaceRetention,
  selectTemplatePackVersion,
  setTemplateWorkspaceArchived,
} from './templateStudioApi';
import './TemplateStudio.css';

export default function TemplateStudioRoute() {
  const [workspaces, setWorkspaces] = useState([]);
  const [archivedWorkspaces, setArchivedWorkspaces] = useState([]);
  const [skippedCorrupt, setSkippedCorrupt] = useState(0);
  const [workspace, setWorkspace] = useState(null);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState(null);

  const load = useCallback(async (preferredId, signal) => {
    setStatus('loading');
    setError(null);
    try {
      const [activePage, archivedPage] = await Promise.all([
        listAllTemplateWorkspaces({ signal, archived: false }),
        listAllTemplateWorkspaces({ signal, archived: true }),
      ]);
      const items = activePage.items || [];
      setWorkspaces(items);
      setArchivedWorkspaces(archivedPage.items || []);
      setSkippedCorrupt(Math.max(activePage.skippedCorrupt || 0, archivedPage.skippedCorrupt || 0));
      if (!items.length) {
        setWorkspace(null);
        setStatus('empty');
        return;
      }
      const selected = items.find((item) => item.workspaceId === preferredId) || items[0];
      const loaded = await getTemplateWorkspace(selected.workspaceId, { signal });
      setWorkspace(loaded);
      setStatus('ready');
    } catch (loadError) {
      if (loadError.name === 'AbortError') return;
      setError(loadError);
      setStatus('error');
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(undefined, controller.signal);
    return () => controller.abort();
  }, [load]);

  async function selectWorkspace(workspaceId) {
    setStatus('loading-workspace');
    setError(null);
    try {
      setWorkspace(await getTemplateWorkspace(workspaceId));
      setStatus('ready');
    } catch (loadError) {
      setError(loadError);
      setStatus('error');
    }
  }

  async function approve({ semantic, anchor, fields }) {
    const updated = await approveTemplateMapping(workspace.workspaceId, semantic, {
      anchor,
      fields,
      expectedRevision: workspace.revision,
    });
    setWorkspace(updated);
    setWorkspaces((items) =>
      items.map((item) =>
        item.workspaceId === updated.workspaceId
          ? {
              ...item,
              revision: updated.revision,
              coveragePercent: updated.coveragePercent,
              status: updated.status,
            }
          : item,
      ),
    );
    return updated;
  }

  async function remove(semantic) {
    const updated = await removeTemplateMapping(
      workspace.workspaceId,
      semantic,
      workspace.revision,
    );
    setWorkspace(updated);
    return updated;
  }

  async function rename(summary, displayName) {
    await renameTemplateWorkspace(summary.workspaceId, displayName, summary.revision);
    await load(workspace?.workspaceId || summary.workspaceId);
  }

  async function clone(summary, values) {
    const created = await cloneTemplateWorkspace(summary.workspaceId, {
      ...values,
      expectedRevision: summary.revision,
    });
    await load(created.workspaceId);
  }

  async function createWorkspace(payload) {
    const created = await createTemplateWorkspace(payload);
    await load(created.workspaceId);
    return created;
  }

  async function setArchived(summary, archived) {
    await setTemplateWorkspaceArchived(summary.workspaceId, archived, summary.revision);
    await load(archived ? undefined : summary.workspaceId);
  }

  async function importDraft(filePayload) {
    const imported = await importTemplateWorkspace(filePayload.filename, filePayload.contentBase64);
    await load(imported.workspaceId);
  }

  async function applyRetention(confirmationToken) {
    const result = await applyTemplateWorkspaceRetention(confirmationToken);
    await load(workspace?.workspaceId);
    return result;
  }

  async function restoreRetention(quarantineId) {
    const result = await restoreTemplateWorkspaceRetention(quarantineId);
    await load(workspace?.workspaceId);
    return result;
  }

  return (
    <TemplateStudioWorkbench
      status={status}
      error={error}
      workspaces={workspaces}
      archivedWorkspaces={archivedWorkspaces}
      skippedCorrupt={skippedCorrupt}
      workspace={workspace}
      onRetry={() => load(workspace?.workspaceId)}
      onSelectWorkspace={selectWorkspace}
      onApprove={approve}
      onRemove={remove}
      onRenameWorkspace={rename}
      onCloneWorkspace={clone}
      onAnalyzeTemplate={analyzeTemplateSource}
      onCreateWorkspace={createWorkspace}
      onSetWorkspaceArchived={setArchived}
      onExportWorkspace={exportTemplateWorkspace}
      onImportWorkspace={importDraft}
      onPreviewRetention={previewTemplateWorkspaceRetention}
      onApplyRetention={applyRetention}
      onRestoreRetention={restoreRetention}
      onLoadCatalog={getTemplatePackCatalog}
      onPreviewCatalogRecovery={previewTemplatePackCatalogRecovery}
      onRecoverCatalog={recoverTemplatePackCatalog}
      onSelectCatalogVersion={selectTemplatePackVersion}
      onListValidationRuns={listTemplateValidationRuns}
      onCreateValidationRun={createTemplateValidationRun}
      onDownloadValidationArtifact={downloadTemplateValidationArtifact}
      onApproveValidationBaseline={approveTemplateValidationBaseline}
      onPublishValidationRun={publishTemplateValidationRun}
    />
  );
}

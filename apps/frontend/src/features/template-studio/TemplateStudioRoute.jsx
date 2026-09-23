import { useCallback, useEffect, useRef, useState } from 'react';
import TemplateStudioWorkbench from './TemplateStudioWorkbench';
import {
  editorDraftApi,
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

export default function TemplateStudioRoute({ onReturn }) {
  const [workspaces, setWorkspaces] = useState([]);
  const [archivedWorkspaces, setArchivedWorkspaces] = useState([]);
  const [skippedCorrupt, setSkippedCorrupt] = useState(0);
  const [workspace, setWorkspace] = useState(null);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState(null);
  const readGeneration = useRef(0);

  const load = useCallback(async (preferredId, signal) => {
    const generation = ++readGeneration.current;
    const isCurrent = () => generation === readGeneration.current && !signal?.aborted;
    setStatus('loading');
    setError(null);
    try {
      const [activePage, archivedPage] = await Promise.all([
        listAllTemplateWorkspaces({ signal, archived: false }),
        listAllTemplateWorkspaces({ signal, archived: true }),
      ]);
      if (!isCurrent()) return;
      const items = activePage.items || [];
      const selected = items.find((item) => item.workspaceId === preferredId) || items[0];
      const loaded = selected ? await getTemplateWorkspace(selected.workspaceId, { signal }) : null;
      if (!isCurrent()) return;
      setWorkspaces(items);
      setArchivedWorkspaces(archivedPage.items || []);
      setSkippedCorrupt(Math.max(activePage.skippedCorrupt || 0, archivedPage.skippedCorrupt || 0));
      if (!items.length) {
        setWorkspace(null);
        setStatus('empty');
        return;
      }
      setWorkspace(loaded);
      setStatus('ready');
    } catch (loadError) {
      if (!isCurrent() || loadError.name === 'AbortError') return;
      setError(loadError);
      setStatus('error');
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(undefined, controller.signal);
    return () => {
      readGeneration.current += 1;
      controller.abort();
    };
  }, [load]);

  async function selectWorkspace(workspaceId) {
    const generation = ++readGeneration.current;
    setStatus('loading-workspace');
    setError(null);
    try {
      const loaded = await getTemplateWorkspace(workspaceId);
      if (generation !== readGeneration.current) return;
      setWorkspace(loaded);
      setStatus('ready');
    } catch (loadError) {
      if (generation !== readGeneration.current || loadError.name === 'AbortError') return;
      setError(loadError);
      setStatus('error');
    }
  }

  async function approve({ semantic, anchor, fields, expectedRevision }) {
    const generation = readGeneration.current;
    const updated = await approveTemplateMapping(workspace.workspaceId, semantic, {
      anchor,
      fields,
      expectedRevision: expectedRevision ?? workspace.revision,
    });
    if (generation === readGeneration.current) {
      setWorkspace((current) =>
        current?.workspaceId === updated.workspaceId && current.revision <= updated.revision
          ? updated
          : current,
      );
    }
    setWorkspaces((items) =>
      items.map((item) =>
        item.workspaceId === updated.workspaceId && item.revision <= updated.revision
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
    const generation = readGeneration.current;
    const updated = await removeTemplateMapping(
      workspace.workspaceId,
      semantic,
      workspace.revision,
    );
    if (generation === readGeneration.current) {
      setWorkspace((current) =>
        current?.workspaceId === updated.workspaceId && current.revision <= updated.revision
          ? updated
          : current,
      );
    }
    setWorkspaces((items) =>
      items.map((item) =>
        item.workspaceId === updated.workspaceId && item.revision <= updated.revision
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
      draftApi={editorDraftApi}
      onReturn={onReturn}
      onNormalized={(created) => load(created.workspaceId)}
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

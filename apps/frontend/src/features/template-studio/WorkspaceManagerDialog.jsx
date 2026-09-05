import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Archive,
  Check,
  Copy,
  Download,
  FilePlus2,
  FileUp,
  FolderOpen,
  Pencil,
  RotateCcw,
  Search,
  ShieldCheck,
  X,
} from 'lucide-react';
import { downloadDraft, readDraftFile } from './draftTransfer';
import NewTemplateWorkspace from './NewTemplateWorkspace';

function reportTypeLabel(value) {
  return (
    {
      full: 'Full',
      server_only: 'Server',
      client_only: 'Client',
      summary: 'Summary',
      technical: 'Technical',
      incident_response: 'Incident Response',
    }[value] || value
  );
}

function statusLabel(value) {
  return (
    {
      analyzed: 'Đã phân tích',
      mapping_incomplete: 'Đang ánh xạ',
      mapping_complete: 'Đủ mapping',
      test_failed: 'Kiểm thử lỗi',
      test_passed: 'Đã kiểm thử',
      published: 'Đã phát hành',
    }[value] || value
  );
}

function updatedLabel(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function bytesLabel(value) {
  const bytes = Number(value) || 0;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

export default function WorkspaceManagerDialog({
  activeWorkspaces = [],
  archivedWorkspaces = [],
  skippedCorrupt = 0,
  currentWorkspaceId,
  onDismiss,
  onOpenWorkspace,
  onRename,
  onClone,
  onAnalyzeTemplate,
  onCreateWorkspace,
  onSetArchived,
  onExport,
  onImport,
  onPreviewRetention,
  onApplyRetention,
  onRestoreRetention,
}) {
  const [tab, setTab] = useState('active');
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState(currentWorkspaceId || '');
  const [action, setAction] = useState(null);
  const [form, setForm] = useState({ displayName: '', profileId: '', version: '0.1.0' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [retentionDays, setRetentionDays] = useState(90);
  const [retentionPlan, setRetentionPlan] = useState(null);
  const [quarantineBatch, setQuarantineBatch] = useState(null);
  const dialogRef = useRef(null);
  const titleRef = useRef(null);
  const fileRef = useRef(null);

  const source = tab === 'active' ? activeWorkspaces : archivedWorkspaces;
  const items = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase('vi');
    if (!normalized) return source;
    return source.filter((item) =>
      `${item.displayName} ${item.profileId} ${item.reportType}`
        .toLocaleLowerCase('vi')
        .includes(normalized),
    );
  }, [query, source]);
  const selected = items.find((item) => item.workspaceId === selectedId) || items[0] || null;
  const retentionDaysValid =
    Number.isInteger(retentionDays) && retentionDays >= 30 && retentionDays <= 3650;

  useEffect(() => {
    if (items.length && !items.some((item) => item.workspaceId === selectedId)) {
      setSelectedId(items[0].workspaceId);
    }
  }, [items, selectedId]);

  useEffect(() => {
    titleRef.current?.focus();
  }, []);

  function handleDialogKeyDown(event) {
    if (event.key === 'Escape') {
      if (action) setAction(null);
      else if (!busy) onDismiss();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = [
      ...dialogRef.current.querySelectorAll(
        'button:not(:disabled), input:not(:disabled), select:not(:disabled), [tabindex="0"]',
      ),
    ].filter((element) => !element.closest('[hidden]'));
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function chooseTab(nextTab) {
    setTab(nextTab);
    setQuery('');
    setAction(null);
    const nextItems = nextTab === 'active' ? activeWorkspaces : archivedWorkspaces;
    setSelectedId(nextItems[0]?.workspaceId || '');
  }

  function beginAction(kind) {
    if (!selected) return;
    setError(null);
    setAction(kind);
    if (kind === 'rename') {
      setForm((current) => ({ ...current, displayName: selected.displayName }));
    }
    if (kind === 'clone') {
      setForm({
        displayName: `${selected.displayName} — bản sao`,
        profileId: `${selected.profileId}-copy`,
        version: selected.version || '0.1.0',
      });
    }
  }

  function beginRetention() {
    setError(null);
    setRetentionPlan(null);
    setQuarantineBatch(null);
    setAction('retention');
  }

  function beginCreate() {
    setError(null);
    setAction('create');
  }

  async function createWorkspace(payload) {
    const created = await onCreateWorkspace(payload);
    onDismiss();
    return created;
  }

  async function run(task, successAction = null, onFailure = null) {
    setBusy(true);
    setError(null);
    try {
      await task();
      setAction(successAction);
    } catch (operationError) {
      setError(operationError);
      onFailure?.(operationError);
    } finally {
      setBusy(false);
    }
  }

  async function submitAction(event) {
    event.preventDefault();
    if (action === 'rename') {
      await run(() => onRename(selected, form.displayName.trim()));
    } else if (action === 'clone') {
      await run(() =>
        onClone(selected, {
          displayName: form.displayName.trim(),
          profileId: form.profileId.trim(),
          version: form.version.trim(),
        }),
      );
    }
  }

  async function importFile(event) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    await run(async () => onImport(await readDraftFile(file)));
  }

  async function exportSelected() {
    await run(async () => downloadDraft(await onExport(selected.workspaceId)));
  }

  async function previewRetention() {
    setQuarantineBatch(null);
    await run(async () => setRetentionPlan(await onPreviewRetention(retentionDays)), 'retention');
  }

  async function applyRetention() {
    await run(
      async () => {
        const result = await onApplyRetention(retentionPlan.confirmationToken);
        setQuarantineBatch(result);
        setRetentionPlan(null);
      },
      'retention',
      (operationError) => {
        if (operationError.conflict) setRetentionPlan(null);
      },
    );
  }

  async function restoreRetention() {
    await run(async () => {
      await onRestoreRetention(quarantineBatch.quarantineId);
      setQuarantineBatch(null);
    }, 'retention');
  }

  return (
    <div
      className="ts-manager-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onDismiss();
      }}
    >
      <section
        className="ts-manager"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ts-manager-title"
        ref={dialogRef}
        onKeyDown={handleDialogKeyDown}
      >
        <header className="ts-manager-head">
          <div>
            <h1 id="ts-manager-title" tabIndex="-1" ref={titleRef}>
              Workspace
            </h1>
            <p>Quản lý draft cục bộ và bản chuyển giao cho team.</p>
          </div>
          <button
            className="ts-icon-button"
            type="button"
            aria-label="Đóng quản lý workspace"
            onClick={onDismiss}
            disabled={busy}
          >
            <X size={18} />
          </button>
        </header>

        <div className="ts-manager-toolbar">
          <button
            className="ts-button ts-button--primary"
            type="button"
            onClick={beginCreate}
            disabled={busy || action === 'create'}
          >
            <FilePlus2 size={15} />
            Template mới
          </button>
          <div className="ts-manager-tabs" role="tablist" aria-label="Trạng thái workspace">
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'active'}
              className={tab === 'active' ? 'active' : ''}
              onClick={() => chooseTab('active')}
            >
              Đang hoạt động <span>{activeWorkspaces.length}</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'archived'}
              className={tab === 'archived' ? 'active' : ''}
              onClick={() => chooseTab('archived')}
            >
              Đã lưu trữ <span>{archivedWorkspaces.length}</span>
            </button>
          </div>
          <div className="ts-manager-search">
            <Search size={15} />
            <label className="sr-only" htmlFor="ts-manager-search">
              Tìm workspace
            </label>
            <input
              id="ts-manager-search"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Tìm workspace"
            />
          </div>
          <input ref={fileRef} type="file" accept=".rptdraft" hidden onChange={importFile} />
          <button
            className="ts-button ts-button--secondary"
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={busy}
          >
            <FileUp size={15} />
            Import draft
          </button>
          <button
            className="ts-button ts-button--secondary"
            type="button"
            onClick={beginRetention}
            disabled={busy}
          >
            <ShieldCheck size={15} />
            Dọn an toàn
          </button>
        </div>

        {error && (
          <div className="ts-manager-error" role="alert">
            <strong>{error.conflict ? 'Workspace đã thay đổi' : 'Thao tác chưa hoàn thành'}</strong>
            <span>{error.message}</span>
            <button type="button" onClick={() => setError(null)}>
              Đóng
            </button>
          </div>
        )}
        {!error && skippedCorrupt > 0 && (
          <div className="ts-manager-warning" role="status">
            {skippedCorrupt} workspace hỏng đã được cô lập khỏi danh sách.
          </div>
        )}

        <div className={`ts-manager-content ${action === 'create' ? 'is-create' : ''}`}>
          {action === 'create' ? (
            <NewTemplateWorkspace
              onCancel={() => setAction(null)}
              onAnalyze={onAnalyzeTemplate}
              onCreate={createWorkspace}
            />
          ) : (
            <>
              <div className="ts-manager-table-wrap">
                {items.length ? (
                  <table className="ts-manager-table">
                    <caption className="sr-only">Danh sách workspace Template Studio</caption>
                    <thead>
                      <tr>
                        <th>Tên workspace</th>
                        <th>Loại</th>
                        <th>Độ phủ</th>
                        <th>Cập nhật</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item) => (
                        <tr
                          key={item.workspaceId}
                          className={item.workspaceId === selected?.workspaceId ? 'selected' : ''}
                        >
                          <td>
                            <button
                              type="button"
                              onClick={() => {
                                setSelectedId(item.workspaceId);
                                setAction(null);
                              }}
                            >
                              <span>{item.displayName}</span>
                              <small>
                                {item.profileId} · v{item.version}
                              </small>
                            </button>
                          </td>
                          <td>{reportTypeLabel(item.reportType)}</td>
                          <td>
                            <span className="ts-manager-coverage">
                              <i style={{ width: `${item.coveragePercent}%` }} />
                            </span>
                            <b>{Math.round(item.coveragePercent)}%</b>
                          </td>
                          <td>{updatedLabel(item.updatedAt)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="ts-manager-empty">
                    <FolderOpen size={24} />
                    <strong>
                      {query
                        ? 'Không tìm thấy workspace'
                        : tab === 'active'
                          ? 'Chưa có workspace đang hoạt động'
                          : 'Chưa có workspace lưu trữ'}
                    </strong>
                    <span>{query ? 'Thử từ khóa khác.' : 'Danh sách này không có dữ liệu.'}</span>
                  </div>
                )}
              </div>

              <aside className="ts-manager-detail" aria-label="Chi tiết workspace đã chọn">
                {action === 'retention' ? (
                  <div className="ts-retention">
                    <div className="ts-retention-head">
                      <span className="ts-manager-state">Có thể khôi phục</span>
                      <h2>Dọn workspace cũ</h2>
                      <p>Chỉ chuyển dữ liệu đủ điều kiện vào vùng cách ly. Không xóa vĩnh viễn.</p>
                    </div>

                    {!quarantineBatch && (
                      <label className="ts-retention-days">
                        Không sử dụng trong
                        <span>
                          <input
                            type="number"
                            min="30"
                            max="3650"
                            value={retentionDays}
                            disabled={busy}
                            onChange={(event) => {
                              setRetentionDays(Number(event.target.value));
                              setRetentionPlan(null);
                            }}
                          />
                          ngày
                        </span>
                      </label>
                    )}

                    {retentionPlan && (
                      <div
                        className={`ts-retention-plan ${retentionPlan.blocked ? 'blocked' : ''}`}
                        role="status"
                      >
                        <strong>
                          {retentionPlan.blocked ? 'Không thể áp dụng' : 'Kết quả xem trước'}
                        </strong>
                        <dl>
                          <div>
                            <dt>Workspace</dt>
                            <dd>{retentionPlan.candidateWorkspaceCount}</dd>
                          </div>
                          <div>
                            <dt>Nguồn DOCX</dt>
                            <dd>{retentionPlan.candidateSourceCount}</dd>
                          </div>
                          <div>
                            <dt>Dung lượng</dt>
                            <dd>{bytesLabel(retentionPlan.reclaimableBytes)}</dd>
                          </div>
                        </dl>
                        {retentionPlan.blockers?.length > 0 && (
                          <ul>
                            {retentionPlan.blockers.map((blocker) => (
                              <li key={blocker}>{blocker}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}

                    {quarantineBatch && (
                      <div className="ts-retention-result" role="status">
                        <Check size={18} />
                        <div>
                          <strong>Đã chuyển vào vùng cách ly</strong>
                          <span>
                            {quarantineBatch.workspaceCount} workspace ·{' '}
                            {quarantineBatch.sourceCount} nguồn
                          </span>
                          <code>{quarantineBatch.quarantineId}</code>
                        </div>
                      </div>
                    )}

                    <div className="ts-retention-actions">
                      <button
                        className="ts-button ts-button--secondary"
                        type="button"
                        onClick={() => setAction(null)}
                        disabled={busy}
                      >
                        Đóng
                      </button>
                      {quarantineBatch ? (
                        <button
                          className="ts-button ts-button--primary"
                          type="button"
                          onClick={restoreRetention}
                          disabled={busy}
                        >
                          <RotateCcw size={15} />
                          {busy ? 'Đang khôi phục…' : 'Khôi phục ngay'}
                        </button>
                      ) : retentionPlan?.confirmationToken && !retentionPlan.blocked ? (
                        <button
                          className="ts-button ts-button--primary"
                          type="button"
                          onClick={applyRetention}
                          disabled={busy}
                        >
                          <Archive size={15} />
                          {busy ? 'Đang cách ly…' : 'Chuyển vào cách ly'}
                        </button>
                      ) : (
                        <button
                          className="ts-button ts-button--primary"
                          type="button"
                          onClick={previewRetention}
                          disabled={busy || !retentionDaysValid}
                        >
                          {busy ? 'Đang kiểm tra…' : 'Xem trước'}
                        </button>
                      )}
                    </div>
                  </div>
                ) : selected ? (
                  <>
                    <div className="ts-manager-summary">
                      <span className={`ts-manager-state ${selected.archived ? 'archived' : ''}`}>
                        {selected.archived ? 'Đã lưu trữ' : statusLabel(selected.status)}
                      </span>
                      <h2>{selected.displayName}</h2>
                      <code>{selected.profileId}</code>
                      <dl>
                        <div>
                          <dt>Report type</dt>
                          <dd>{reportTypeLabel(selected.reportType)}</dd>
                        </div>
                        <div>
                          <dt>Coverage</dt>
                          <dd>{Math.round(selected.coveragePercent)}%</dd>
                        </div>
                        <div>
                          <dt>Revision</dt>
                          <dd>{selected.revision}</dd>
                        </div>
                      </dl>
                    </div>

                    {!action && (
                      <div className="ts-manager-actions">
                        {!selected.archived && (
                          <button
                            className="ts-button ts-button--primary"
                            type="button"
                            onClick={() => onOpenWorkspace(selected.workspaceId)}
                            disabled={busy}
                          >
                            <FolderOpen size={15} />
                            Mở workspace
                          </button>
                        )}
                        {!selected.archived && (
                          <button type="button" onClick={() => beginAction('rename')}>
                            <Pencil size={15} />
                            Đổi tên
                          </button>
                        )}
                        {!selected.archived && (
                          <button type="button" onClick={() => beginAction('clone')}>
                            <Copy size={15} />
                            Tạo bản sao
                          </button>
                        )}
                        <button type="button" onClick={exportSelected} disabled={busy}>
                          <Download size={15} />
                          Export draft
                        </button>
                        {selected.archived ? (
                          <button type="button" onClick={() => beginAction('restore')}>
                            <RotateCcw size={15} />
                            Khôi phục
                          </button>
                        ) : (
                          <button
                            className="danger"
                            type="button"
                            onClick={() => beginAction('archive')}
                          >
                            <Archive size={15} />
                            Lưu trữ
                          </button>
                        )}
                      </div>
                    )}

                    {(action === 'rename' || action === 'clone') && (
                      <form className="ts-manager-form" onSubmit={submitAction}>
                        <strong>{action === 'rename' ? 'Đổi tên workspace' : 'Tạo bản sao'}</strong>
                        <label>
                          Tên hiển thị
                          <input
                            autoFocus
                            value={form.displayName}
                            maxLength="200"
                            required
                            onChange={(event) =>
                              setForm((current) => ({
                                ...current,
                                displayName: event.target.value,
                              }))
                            }
                          />
                        </label>
                        {action === 'clone' && (
                          <>
                            <label>
                              Profile ID
                              <input
                                value={form.profileId}
                                required
                                pattern="[a-z0-9][a-z0-9._-]{1,127}"
                                onChange={(event) =>
                                  setForm((current) => ({
                                    ...current,
                                    profileId: event.target.value,
                                  }))
                                }
                              />
                            </label>
                            <label>
                              Version
                              <input
                                value={form.version}
                                required
                                onChange={(event) =>
                                  setForm((current) => ({
                                    ...current,
                                    version: event.target.value,
                                  }))
                                }
                              />
                            </label>
                          </>
                        )}
                        <div>
                          <button
                            className="ts-button ts-button--secondary"
                            type="button"
                            onClick={() => setAction(null)}
                            disabled={busy}
                          >
                            Hủy
                          </button>
                          <button
                            className="ts-button ts-button--primary"
                            type="submit"
                            disabled={busy || !form.displayName.trim()}
                          >
                            {busy ? 'Đang lưu…' : action === 'rename' ? 'Lưu tên' : 'Tạo bản sao'}
                          </button>
                        </div>
                      </form>
                    )}

                    {(action === 'archive' || action === 'restore') && (
                      <div className="ts-manager-confirm" role="alert">
                        <strong>
                          {action === 'archive'
                            ? 'Lưu trữ workspace này?'
                            : 'Khôi phục workspace này?'}
                        </strong>
                        <span>
                          {action === 'archive'
                            ? 'Workspace sẽ chuyển sang chế độ chỉ đọc, không bị xóa.'
                            : 'Workspace sẽ trở lại danh sách đang hoạt động.'}
                        </span>
                        <div>
                          <button
                            className="ts-button ts-button--secondary"
                            type="button"
                            onClick={() => setAction(null)}
                            disabled={busy}
                          >
                            Hủy
                          </button>
                          <button
                            className={`ts-button ${action === 'archive' ? 'ts-button--danger' : 'ts-button--primary'}`}
                            type="button"
                            disabled={busy}
                            onClick={() => run(() => onSetArchived(selected, action === 'archive'))}
                          >
                            {busy ? 'Đang xử lý…' : action === 'archive' ? 'Lưu trữ' : 'Khôi phục'}
                          </button>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="ts-manager-empty">
                    <Check size={24} />
                    <strong>Chọn một workspace</strong>
                  </div>
                )}
              </aside>
            </>
          )}
        </div>
      </section>
    </div>
  );
}

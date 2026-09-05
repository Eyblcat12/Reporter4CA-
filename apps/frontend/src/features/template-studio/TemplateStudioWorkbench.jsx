import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronRight,
  FileStack,
  FlaskConical,
  FolderCog,
  LoaderCircle,
  LockKeyhole,
  Moon,
  PackageOpen,
  Search,
  Sun,
  X,
} from 'lucide-react';
import { useTheme } from '../../hooks/useTheme';
import { anchorKey, anchorOptionsForSemantic } from './anchorCatalog';
import { semanticDefinition } from './semanticCatalog';
import CatalogDialog from './CatalogDialog';
import ValidationDialog from './ValidationDialog';
import WorkspaceManagerDialog from './WorkspaceManagerDialog';

function workspaceRows(workspace) {
  if (!workspace) return [];
  const checklist = workspace.analysis?.mapping?.checklist || [];
  const slots = new Map((workspace.slots || []).map((slot) => [slot.semantic, slot]));
  return checklist.map((item) => {
    const definition = semanticDefinition(item.semantic);
    const anchorCatalog = anchorOptionsForSemantic(
      workspace,
      item.semantic,
      item.suggestedAnchors || [],
    );
    return {
      ...definition,
      semantic: item.semantic,
      required: item.required !== false,
      suggestions: item.suggestedAnchors || [],
      anchorOptions: anchorCatalog.options,
      ambiguousAnchorCount: anchorCatalog.ambiguousCount,
      slot: slots.get(item.semantic) || null,
    };
  });
}

function initialDraft(row) {
  const anchor =
    row?.slot?.anchor ||
    row?.anchorOptions?.find((item) => item.recommended && !item.usedBy) ||
    null;
  const mappedFields = new Map(
    (row?.slot?.fields || []).map((field) => [field.source, field.target]),
  );
  return {
    anchorKey: anchor ? `${anchor.kind}:${anchor.value}` : '',
    fields: Object.fromEntries(
      (row?.fields || []).map((field) => [field, mappedFields.get(field) || '']),
    ),
  };
}

function anchorFromKey(value) {
  const separator = value.indexOf(':');
  if (separator < 1) return null;
  return { kind: value.slice(0, separator), value: value.slice(separator + 1) };
}

function useCompactDrawer() {
  const [compact, setCompact] = useState(() => window.matchMedia('(max-width: 1120px)').matches);
  useEffect(() => {
    const query = window.matchMedia('(max-width: 1120px)');
    const update = () => setCompact(query.matches);
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  return compact;
}

function EmptyWorkspace({ onRetry, onManage }) {
  return (
    <div className="ts-state" role="status">
      <FileStack size={28} aria-hidden="true" />
      <h1>Chưa có workspace</h1>
      <p>Phân tích một template Word để bắt đầu ánh xạ semantic.</p>
      <div className="ts-state-actions">
        <button className="ts-button ts-button--primary" type="button" onClick={onManage}>
          Quản lý workspace
        </button>
        <button className="ts-button ts-button--secondary" type="button" onClick={onRetry}>
          Tải lại
        </button>
      </div>
    </div>
  );
}

function LoadingWorkspace() {
  return (
    <div className="ts-loading" role="status" aria-live="polite">
      <span className="sr-only">Đang tải workspace Template Studio</span>
      {Array.from({ length: 7 }, (_, index) => (
        <i key={index} />
      ))}
    </div>
  );
}

function ErrorWorkspace({ error, onRetry }) {
  return (
    <div className="ts-state ts-state--error" role="alert">
      <AlertTriangle size={28} aria-hidden="true" />
      <h1>Không tải được Template Studio</h1>
      <p>{error?.message || 'Backend không phản hồi.'}</p>
      <button className="ts-button ts-button--primary" type="button" onClick={onRetry}>
        Thử lại
      </button>
    </div>
  );
}

export default function TemplateStudioWorkbench({
  status,
  error,
  workspaces,
  archivedWorkspaces,
  skippedCorrupt,
  workspace,
  onRetry,
  onSelectWorkspace,
  onApprove,
  onRemove,
  onRenameWorkspace,
  onCloneWorkspace,
  onAnalyzeTemplate,
  onCreateWorkspace,
  onSetWorkspaceArchived,
  onExportWorkspace,
  onImportWorkspace,
  onPreviewRetention,
  onApplyRetention,
  onRestoreRetention,
  onLoadCatalog,
  onPreviewCatalogRecovery,
  onRecoverCatalog,
  onSelectCatalogVersion,
  onListValidationRuns,
  onCreateValidationRun,
  onDownloadValidationArtifact,
  onApproveValidationBaseline,
  onPublishValidationRun,
}) {
  const { theme, toggleTheme } = useTheme();
  const compactDrawer = useCompactDrawer();
  const rows = useMemo(() => workspaceRows(workspace), [workspace]);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [selectedSemantic, setSelectedSemantic] = useState('');
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [draft, setDraft] = useState({ anchorKey: '', fields: {} });
  const [anchorQuery, setAnchorQuery] = useState('');
  const [operation, setOperation] = useState('idle');
  const [operationError, setOperationError] = useState(null);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [managerOpen, setManagerOpen] = useState(false);
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [validationOpen, setValidationOpen] = useState(false);
  const inspectorRef = useRef(null);
  const inspectorTitleRef = useRef(null);
  const lastTriggerRef = useRef(null);
  const managerTriggerRef = useRef(null);
  const catalogTriggerRef = useRef(null);
  const validationTriggerRef = useRef(null);

  const selected = rows.find((row) => row.semantic === selectedSemantic) || null;
  const filteredRows = rows.filter((row) => {
    const mapped = Boolean(row.slot);
    const matchesFilter =
      filter === 'all' || (filter === 'mapped' && mapped) || (filter === 'missing' && !mapped);
    const haystack = `${row.label} ${row.semantic} ${row.source}`.toLocaleLowerCase('vi');
    return matchesFilter && haystack.includes(query.trim().toLocaleLowerCase('vi'));
  });
  const mappedCount = rows.filter((row) => row.slot).length;
  const missingCount = rows.length - mappedCount;
  const coverage = rows.length ? Math.round((mappedCount / rows.length) * 100) : 0;

  useEffect(() => {
    if (!rows.length) {
      setSelectedSemantic('');
      setInspectorOpen(false);
      return;
    }
    if (!rows.some((row) => row.semantic === selectedSemantic)) {
      const next = rows.find((row) => !row.slot) || rows[0];
      setSelectedSemantic(next.semantic);
      setDraft(initialDraft(next));
    }
  }, [rows, selectedSemantic]);

  useEffect(() => {
    if (!compactDrawer || !inspectorOpen) return undefined;
    const drawer = inspectorRef.current;
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        closeInspector();
        return;
      }
      if (event.key !== 'Tab') return;
      const focusable = [
        ...drawer.querySelectorAll(
          'button:not(:disabled), select:not(:disabled), input:not(:disabled), summary, [tabindex="0"]',
        ),
      ];
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
    };
    drawer.addEventListener('keydown', handleKeyDown);
    return () => drawer.removeEventListener('keydown', handleKeyDown);
  });

  function openInspector(row, trigger) {
    setSelectedSemantic(row.semantic);
    setDraft(initialDraft(row));
    setOperationError(null);
    setConfirmRemove(false);
    setAnchorQuery('');
    setInspectorOpen(true);
    lastTriggerRef.current = trigger;
    if (compactDrawer) window.setTimeout(() => inspectorTitleRef.current?.focus(), 0);
  }

  function closeInspector() {
    setInspectorOpen(false);
    setConfirmRemove(false);
    window.setTimeout(() => lastTriggerRef.current?.focus(), 0);
  }

  function closeManager() {
    setManagerOpen(false);
    window.setTimeout(() => managerTriggerRef.current?.focus(), 0);
  }

  function closeCatalog() {
    setCatalogOpen(false);
    window.setTimeout(() => catalogTriggerRef.current?.focus(), 0);
  }

  function closeValidation() {
    setValidationOpen(false);
    window.setTimeout(() => validationTriggerRef.current?.focus(), 0);
  }

  async function openManagedWorkspace(workspaceId) {
    await onSelectWorkspace(workspaceId);
    closeManager();
  }

  async function saveMapping() {
    const anchor = anchorFromKey(draft.anchorKey);
    if (!selected || !anchor || operation === 'saving') return;
    setOperation('saving');
    setOperationError(null);
    try {
      await onApprove({
        semantic: selected.semantic,
        anchor,
        fields: selected.fields.map((source) => ({ source, target: draft.fields[source] })),
      });
      setOperation('saved');
    } catch (saveError) {
      setOperation('idle');
      setOperationError(saveError);
    }
  }

  async function removeMapping() {
    if (!selected?.slot || operation === 'saving') return;
    setOperation('saving');
    setOperationError(null);
    try {
      await onRemove(selected.semantic);
      setDraft(initialDraft({ ...selected, slot: null }));
      setConfirmRemove(false);
      setOperation('saved');
    } catch (removeError) {
      setOperation('idle');
      setOperationError(removeError);
    }
  }

  function nextBlocker(event) {
    const blocker = rows.find((row) => !row.slot);
    if (blocker) openInspector(blocker, event.currentTarget);
  }

  const fieldMappingsValid = selected?.fields.every((field) =>
    /^column:\d+$/.test(draft.fields[field] || ''),
  );
  const selectedAnchorOption = selected?.anchorOptions.find(
    (anchor) => anchorKey(anchor) === draft.anchorKey,
  );
  const canSave =
    Boolean(draft.anchorKey) &&
    !selectedAnchorOption?.usedBy &&
    fieldMappingsValid &&
    operation !== 'saving';
  const normalizedAnchorQuery = anchorQuery.trim().toLocaleLowerCase('vi');
  const visibleAnchorOptions = (selected?.anchorOptions || []).filter(
    (anchor) =>
      !normalizedAnchorQuery ||
      `${anchor.value} ${anchor.kind}`
        .replace(/[_{}.-]+/g, ' ')
        .toLocaleLowerCase('vi')
        .includes(normalizedAnchorQuery) ||
      anchorKey(anchor) === draft.anchorKey,
  );
  const recommendedAnchors = visibleAnchorOptions.filter(
    (anchor) => anchor.recommended && !anchor.usedBy,
  );
  const availableAnchors = visibleAnchorOptions.filter(
    (anchor) => !anchor.recommended && !anchor.usedBy,
  );
  const usedAnchors = visibleAnchorOptions.filter((anchor) => anchor.usedBy);
  const contentState = status === 'loading' || status === 'loading-workspace' ? 'loading' : status;

  return (
    <div className="ts-app">
      <header className="ts-topbar">
        <div className="ts-brand">
          <span>R</span>
          <strong>Template Studio</strong>
        </div>
        <div className="ts-context">
          <label className="sr-only" htmlFor="ts-workspace">
            Workspace hiện tại
          </label>
          <select
            id="ts-workspace"
            value={workspace?.workspaceId || ''}
            disabled={!workspace || status === 'loading-workspace'}
            onChange={(event) => onSelectWorkspace(event.target.value)}
          >
            {workspaces.map((item) => (
              <option key={item.workspaceId} value={item.workspaceId}>
                {item.displayName}
              </option>
            ))}
          </select>
          <button
            className="ts-manage-button"
            type="button"
            ref={managerTriggerRef}
            onClick={() => setManagerOpen(true)}
            aria-label="Quản lý"
          >
            <FolderCog size={15} aria-hidden="true" />
            <span>Quản lý</span>
          </button>
          <button
            className="ts-manage-button"
            type="button"
            ref={catalogTriggerRef}
            onClick={() => setCatalogOpen(true)}
            aria-label="Catalog"
          >
            <PackageOpen size={15} aria-hidden="true" />
            <span>Catalog</span>
          </button>
          <button
            className="ts-manage-button"
            type="button"
            ref={validationTriggerRef}
            onClick={() => setValidationOpen(true)}
            disabled={!workspace || status === 'loading-workspace'}
            aria-label="Kiểm thử"
          >
            <FlaskConical size={15} aria-hidden="true" />
            <span>Kiểm thử</span>
          </button>
          <span className="ts-draft-badge">Bản nháp</span>
          <button
            className="ts-icon-button"
            type="button"
            onClick={toggleTheme}
            aria-label={
              theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'
            }
          >
            {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
          </button>
        </div>
      </header>

      <nav className="ts-workflow" aria-label="Quy trình chuẩn hóa template">
        {['Phân tích', 'Ánh xạ', 'Rà soát', 'Kiểm thử', 'Phát hành'].map((step, index) => (
          <div
            key={step}
            className={`ts-step ${index === 0 ? 'done' : ''} ${index === 1 ? 'current' : ''}`}
            aria-current={index === 1 ? 'step' : undefined}
          >
            <span>{index === 0 ? <Check size={13} /> : index + 1}</span>
            {step}
          </div>
        ))}
      </nav>

      <main className={`ts-workspace ${inspectorOpen ? 'has-inspector' : ''}`}>
        <section
          className="ts-primary"
          aria-labelledby="ts-page-title"
          inert={compactDrawer && inspectorOpen ? '' : undefined}
        >
          {contentState === 'loading' && <LoadingWorkspace />}
          {contentState === 'empty' && (
            <EmptyWorkspace onRetry={onRetry} onManage={() => setManagerOpen(true)} />
          )}
          {contentState === 'error' && <ErrorWorkspace error={error} onRetry={onRetry} />}
          {contentState === 'ready' && workspace && (
            <>
              <div className="ts-page-head">
                <div>
                  <h1 id="ts-page-title">Ánh xạ template</h1>
                  <p>Kết nối Word anchor với dữ liệu báo cáo chuẩn hóa.</p>
                </div>
                <button
                  className={`ts-button ${inspectorOpen ? 'ts-button--secondary' : 'ts-button--primary'}`}
                  type="button"
                  onClick={nextBlocker}
                  disabled={!missingCount}
                >
                  {missingCount ? 'Blocker tiếp theo' : 'Sẵn sàng rà soát'}
                  <ChevronRight size={16} />
                </button>
              </div>

              <div className="ts-coverage">
                <div>
                  <div className="ts-coverage-label">
                    <strong>Độ phủ bắt buộc</strong>
                    <span>
                      {mappedCount}/{rows.length} block
                    </span>
                  </div>
                  <div
                    className="ts-progress"
                    role="progressbar"
                    aria-label="Độ phủ semantic bắt buộc"
                    aria-valuemin="0"
                    aria-valuemax="100"
                    aria-valuenow={coverage}
                  >
                    <i style={{ width: `${coverage}%` }} />
                  </div>
                </div>
                <div className="ts-metrics">
                  <span>
                    <b>{mappedCount}</b>Đã xong
                  </span>
                  <span className="warning">
                    <b>{missingCount}</b>Blocker
                  </span>
                  <span>
                    <b>{workspace.revision}</b>Revision
                  </span>
                </div>
              </div>

              <div className="ts-toolbar">
                <div className="ts-search">
                  <Search size={16} aria-hidden="true" />
                  <label className="sr-only" htmlFor="ts-search">
                    Tìm block
                  </label>
                  <input
                    id="ts-search"
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Tìm block hoặc nguồn dữ liệu"
                  />
                </div>
                {[
                  ['all', 'Tất cả'],
                  ['missing', 'Blocker'],
                  ['mapped', 'Đã xong'],
                ].map(([value, label]) => (
                  <button
                    key={value}
                    className={`ts-filter ${filter === value ? 'active' : ''}`}
                    type="button"
                    aria-pressed={filter === value}
                    onClick={() => setFilter(value)}
                  >
                    {label}
                  </button>
                ))}
                <span className="ts-result-count" role="status" aria-live="polite">
                  {filteredRows.length} block
                </span>
              </div>

              <div className="ts-table-wrap">
                {filteredRows.length ? (
                  <table className="ts-table">
                    <caption className="sr-only">Các block semantic trong template</caption>
                    <thead>
                      <tr>
                        <th>Block báo cáo</th>
                        <th>Nguồn dữ liệu</th>
                        <th>Word anchor</th>
                        <th>Trạng thái</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredRows.map((row) => {
                        const active = inspectorOpen && row.semantic === selectedSemantic;
                        return (
                          <tr key={row.semantic} className={active ? 'selected' : ''}>
                            <td>
                              <button
                                type="button"
                                className="ts-row-button"
                                aria-controls="ts-inspector"
                                aria-expanded={active}
                                onClick={(event) => openInspector(row, event.currentTarget)}
                              >
                                <span className="ts-block-mark">
                                  {row.renderer.slice(0, 2).toUpperCase()}
                                </span>
                                <span>
                                  <strong>{row.label}</strong>
                                  <small>{row.semantic}</small>
                                </span>
                              </button>
                            </td>
                            <td>
                              <strong>{row.source.split('.').pop().replaceAll('_', ' ')}</strong>
                              <small>{row.source}</small>
                            </td>
                            <td>
                              <strong>{row.slot?.anchor?.value || 'Chưa chọn'}</strong>
                              <small>
                                {row.slot
                                  ? row.slot.anchor.kind.replace('_', ' ')
                                  : 'Cần anchor duy nhất'}
                              </small>
                            </td>
                            <td>
                              <span className={`ts-status ${row.slot ? 'mapped' : 'missing'}`}>
                                {row.slot ? <Check size={13} /> : <AlertTriangle size={13} />}
                                {row.slot ? 'Đã xong' : 'Blocker'}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                ) : (
                  <div className="ts-no-results">
                    <strong>Không tìm thấy block phù hợp</strong>
                    <span>Thử từ khóa khác hoặc đặt lại bộ lọc.</span>
                  </div>
                )}
              </div>
            </>
          )}
        </section>

        <button
          className={`ts-scrim ${compactDrawer && inspectorOpen ? 'visible' : ''}`}
          type="button"
          aria-label="Đóng chi tiết ánh xạ"
          onClick={closeInspector}
        />
        {inspectorOpen && selected && (
          <aside
            className="ts-inspector"
            id="ts-inspector"
            ref={inspectorRef}
            aria-labelledby="ts-inspector-title"
          >
            <div className="ts-inspector-head">
              <div>
                <h2 id="ts-inspector-title" tabIndex="-1" ref={inspectorTitleRef}>
                  {selected.label}
                </h2>
                <p>{selected.semantic}</p>
              </div>
              <span className="ts-required">Bắt buộc</span>
              <button
                className="ts-icon-button ts-inspector-close"
                type="button"
                aria-label="Đóng chi tiết ánh xạ"
                onClick={closeInspector}
              >
                <X size={17} />
              </button>
            </div>
            <div className="ts-inspector-body">
              {operationError && (
                <div
                  className={`ts-message ${operationError.conflict ? 'warning' : 'error'}`}
                  role={operationError.conflict ? 'status' : 'alert'}
                >
                  <AlertTriangle size={17} />
                  <div>
                    <strong>
                      {operationError.conflict
                        ? 'Workspace có revision mới'
                        : 'Chưa lưu được thay đổi'}
                    </strong>
                    <span>{operationError.message} Draft vẫn được giữ.</span>
                  </div>
                  <button type="button" onClick={onRetry}>
                    Tải lại
                  </button>
                </div>
              )}
              <div className="ts-field">
                <div className="ts-anchor-head">
                  <label htmlFor="ts-anchor">Word anchor</label>
                  <span>
                    {selected.anchorOptions.filter((anchor) => !anchor.usedBy).length} khả dụng
                    {selected.ambiguousAnchorCount
                      ? ` · ${selected.ambiguousAnchorCount} trùng`
                      : ''}
                  </span>
                </div>
                {selected.anchorOptions.length > 8 && (
                  <input
                    className="ts-anchor-search"
                    type="search"
                    value={anchorQuery}
                    placeholder="Tìm theo tên hoặc loại anchor"
                    aria-label="Tìm Word anchor"
                    onChange={(event) => setAnchorQuery(event.target.value)}
                  />
                )}
                <select
                  id="ts-anchor"
                  value={draft.anchorKey}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, anchorKey: event.target.value }))
                  }
                >
                  <option value="">Chọn anchor đã phân tích</option>
                  {recommendedAnchors.length > 0 && (
                    <optgroup label="Gợi ý phù hợp">
                      {recommendedAnchors.map((anchor) => (
                        <option key={anchorKey(anchor)} value={anchorKey(anchor)}>
                          {anchor.value} · {anchor.kind.replace('_', ' ')}
                        </option>
                      ))}
                    </optgroup>
                  )}
                  {availableAnchors.length > 0 && (
                    <optgroup label="Anchor khác">
                      {availableAnchors.map((anchor) => (
                        <option key={anchorKey(anchor)} value={anchorKey(anchor)}>
                          {anchor.value} · {anchor.kind.replace('_', ' ')}
                        </option>
                      ))}
                    </optgroup>
                  )}
                  {usedAnchors.length > 0 && (
                    <optgroup label="Đã dùng cho block khác">
                      {usedAnchors.map((anchor) => (
                        <option key={anchorKey(anchor)} value={anchorKey(anchor)} disabled>
                          {anchor.value} · {semanticDefinition(anchor.usedBy).label}
                        </option>
                      ))}
                    </optgroup>
                  )}
                </select>
                {normalizedAnchorQuery && visibleAnchorOptions.length === 0 && (
                  <small className="ts-anchor-empty">Không có anchor phù hợp từ khóa.</small>
                )}
              </div>
              <div className="ts-field">
                <span className="ts-field-label">Nguồn dữ liệu</span>
                <div className="ts-readonly">
                  <code>{selected.source}</code>
                  <LockKeyhole size={14} />
                </div>
              </div>
              {selected.fields.length > 0 && (
                <div className="ts-field">
                  <span className="ts-field-label">Ánh xạ cột</span>
                  <div className="ts-field-map">
                    {selected.fields.map((source, index) => (
                      <label key={source}>
                        <span>
                          <code>{source}</code>
                          <ArrowRight size={13} />
                        </span>
                        <input
                          value={draft.fields[source] || ''}
                          placeholder={`column:${index + 1}`}
                          aria-label={`Cột Word cho ${source}`}
                          onChange={(event) =>
                            setDraft((current) => ({
                              ...current,
                              fields: { ...current.fields, [source]: event.target.value },
                            }))
                          }
                        />
                      </label>
                    ))}
                  </div>
                </div>
              )}
              <div
                className={`ts-validation ${canSave ? 'ready' : ''}`}
                role="status"
                aria-live="polite"
              >
                <span>{canSave ? <Check size={15} /> : <AlertTriangle size={15} />}</span>
                <div>
                  <strong>{canSave ? 'Sẵn sàng duyệt' : 'Ánh xạ chưa hoàn chỉnh'}</strong>
                  <small>
                    {canSave
                      ? 'Lưu sẽ tạo workspace revision mới.'
                      : 'Chọn anchor và hoàn thiện các cột bắt buộc.'}
                  </small>
                </div>
              </div>
              <details className="ts-details">
                <summary>Chi tiết kỹ thuật</summary>
                <dl>
                  <div>
                    <dt>Renderer</dt>
                    <dd>{selected.renderer}</dd>
                  </div>
                  <div>
                    <dt>Workspace revision</dt>
                    <dd>{workspace.revision}</dd>
                  </div>
                </dl>
              </details>
            </div>
            {confirmRemove && (
              <div className="ts-confirm" role="alert">
                <strong>Gỡ ánh xạ block này?</strong>
                <span>Block sẽ trở thành blocker và tạo revision mới.</span>
                <div>
                  <button
                    className="ts-button ts-button--secondary"
                    type="button"
                    onClick={() => setConfirmRemove(false)}
                  >
                    Giữ lại
                  </button>
                  <button
                    className="ts-button ts-button--danger"
                    type="button"
                    onClick={removeMapping}
                  >
                    Gỡ ánh xạ
                  </button>
                </div>
              </div>
            )}
            <div className="ts-inspector-footer">
              <span role="status" aria-live="polite">
                {operation === 'saving' ? (
                  <>
                    <LoaderCircle className="spin" size={14} />
                    Đang lưu…
                  </>
                ) : operation === 'saved' ? (
                  'Đã lưu'
                ) : (
                  `rev. ${workspace.revision}`
                )}
              </span>
              {selected.slot && (
                <button
                  className="ts-button ts-button--danger"
                  type="button"
                  disabled={operation === 'saving'}
                  onClick={() => setConfirmRemove(true)}
                >
                  Gỡ
                </button>
              )}
              <button
                className="ts-button ts-button--primary"
                type="button"
                disabled={!canSave}
                onClick={saveMapping}
              >
                {operation === 'saving' ? 'Đang lưu…' : 'Duyệt ánh xạ'}
              </button>
            </div>
          </aside>
        )}
      </main>
      <footer className="ts-statusbar">
        <span>
          <LockKeyhole size={13} />
          Luồng mặc định được bảo vệ
        </span>
        <span>Template Pack chưa nối Generate</span>
        <span>workspace rev. {workspace?.revision || '—'}</span>
      </footer>
      {managerOpen && (
        <WorkspaceManagerDialog
          activeWorkspaces={workspaces}
          archivedWorkspaces={archivedWorkspaces}
          skippedCorrupt={skippedCorrupt}
          currentWorkspaceId={workspace?.workspaceId}
          onDismiss={closeManager}
          onOpenWorkspace={openManagedWorkspace}
          onRename={onRenameWorkspace}
          onClone={onCloneWorkspace}
          onAnalyzeTemplate={onAnalyzeTemplate}
          onCreateWorkspace={onCreateWorkspace}
          onSetArchived={onSetWorkspaceArchived}
          onExport={onExportWorkspace}
          onImport={onImportWorkspace}
          onPreviewRetention={onPreviewRetention}
          onApplyRetention={onApplyRetention}
          onRestoreRetention={onRestoreRetention}
        />
      )}
      {catalogOpen && (
        <CatalogDialog
          onDismiss={closeCatalog}
          onLoad={onLoadCatalog}
          onPreviewRecovery={onPreviewCatalogRecovery}
          onRecover={onRecoverCatalog}
          onSelectVersion={onSelectCatalogVersion}
        />
      )}
      {validationOpen && workspace && (
        <ValidationDialog
          workspace={workspace}
          onDismiss={closeValidation}
          onListRuns={onListValidationRuns}
          onCreateRun={onCreateValidationRun}
          onDownloadArtifact={onDownloadValidationArtifact}
          onApproveBaseline={onApproveValidationBaseline}
          onPublish={onPublishValidationRun}
          onLoadCatalog={onLoadCatalog}
        />
      )}
    </div>
  );
}

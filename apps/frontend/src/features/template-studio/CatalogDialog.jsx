import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, Database, RefreshCcw, ShieldAlert, ShieldCheck, X } from 'lucide-react';

function versionRows(catalog) {
  return Object.entries(catalog?.packs || {}).flatMap(([packId, pack]) =>
    Object.entries(pack.versions || {}).map(([version, metadata]) => ({
      packId,
      version,
      active: pack.activeVersion === version,
      activeVersion: pack.activeVersion,
      ...metadata,
    })),
  );
}

function versionAction(row) {
  if (row.active) return null;
  if (
    row.activeVersion &&
    row.version.localeCompare(row.activeVersion, undefined, { numeric: true }) < 0
  ) {
    return 'rollback';
  }
  return 'activate';
}

function healthLabel(health) {
  if (!health?.exists) return 'Chưa có';
  return health.valid ? 'Hợp lệ' : 'Không hợp lệ';
}

export default function CatalogDialog({
  onDismiss,
  onLoad,
  onPreviewRecovery,
  onRecover,
  onSelectVersion,
}) {
  const [catalog, setCatalog] = useState(null);
  const [recovery, setRecovery] = useState(null);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState(null);
  const [confirmRecovery, setConfirmRecovery] = useState(false);
  const [recovered, setRecovered] = useState(false);
  const [pendingVersion, setPendingVersion] = useState(null);
  const [selectionNotice, setSelectionNotice] = useState('');
  const dialogRef = useRef(null);
  const titleRef = useRef(null);
  const rows = useMemo(() => versionRows(catalog), [catalog]);

  async function load() {
    setStatus('loading');
    setError(null);
    const [catalogResult, recoveryResult] = await Promise.allSettled([
      onLoad(),
      onPreviewRecovery(),
    ]);
    if (catalogResult.status === 'fulfilled') setCatalog(catalogResult.value);
    else setCatalog(null);
    if (recoveryResult.status === 'fulfilled') setRecovery(recoveryResult.value);
    else setRecovery(null);
    const failure =
      catalogResult.status === 'rejected'
        ? catalogResult.reason
        : recoveryResult.status === 'rejected'
          ? recoveryResult.reason
          : null;
    setError(failure);
    setStatus('ready');
  }

  useEffect(() => {
    titleRef.current?.focus();
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function handleKeyDown(event) {
    if (event.key === 'Escape') {
      if (pendingVersion) setPendingVersion(null);
      else if (confirmRecovery) setConfirmRecovery(false);
      else if (!busy) onDismiss();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = [
      ...dialogRef.current.querySelectorAll('button:not(:disabled), [tabindex="0"]'),
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
  }

  async function recover() {
    setStatus('recovering');
    setError(null);
    try {
      await onRecover(recovery.confirmationToken);
      setRecovered(true);
      setConfirmRecovery(false);
      await load();
    } catch (operationError) {
      setError(operationError);
      setStatus('ready');
      if (operationError.conflict) setConfirmRecovery(false);
    }
  }

  async function selectVersion() {
    setStatus('selecting');
    setError(null);
    try {
      await onSelectVersion(
        pendingVersion.packId,
        pendingVersion.version,
        catalog.revision,
        pendingVersion.action,
      );
      setSelectionNotice(
        `${pendingVersion.action === 'rollback' ? 'Đã rollback' : 'Đã kích hoạt'} v${pendingVersion.version} trong Template Studio.`,
      );
      setPendingVersion(null);
      await load();
    } catch (operationError) {
      if (operationError.conflict) await load();
      setError(operationError);
      setStatus('ready');
      setPendingVersion(null);
    }
  }

  const busy = status === 'loading' || status === 'recovering' || status === 'selecting';

  return (
    <div className="ts-manager-backdrop" role="presentation">
      <section
        className="ts-catalog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ts-catalog-title"
        ref={dialogRef}
        onKeyDown={handleKeyDown}
      >
        <header className="ts-manager-head">
          <div>
            <h1 id="ts-catalog-title" tabIndex="-1" ref={titleRef}>
              Template Pack Catalog
            </h1>
            <p>Kho version tách biệt, chưa kết nối luồng Generate mặc định.</p>
          </div>
          <button
            className="ts-icon-button"
            type="button"
            aria-label="Đóng catalog"
            onClick={onDismiss}
            disabled={busy}
          >
            <X size={18} />
          </button>
        </header>

        {error && (
          <div className="ts-manager-error" role="alert">
            <strong>
              {error.conflict ? 'Catalog đã thay đổi' : 'Thao tác catalog chưa hoàn thành'}
            </strong>
            <span>{error.message}</span>
            <button type="button" onClick={load} disabled={busy}>
              Thử lại
            </button>
          </div>
        )}
        {recovered && !error && (
          <div className="ts-catalog-success" role="status">
            <Check size={15} /> Catalog đã được khôi phục từ checkpoint đã kiểm tra.
          </div>
        )}
        {selectionNotice && !error && (
          <div className="ts-catalog-success" role="status">
            <Check size={15} /> {selectionNotice} Generate mặc định không thay đổi.
          </div>
        )}

        <div className="ts-catalog-body">
          <section className="ts-catalog-main" aria-label="Phiên bản Template Pack">
            <div className="ts-catalog-section-head">
              <div>
                <span>Catalog revision</span>
                <strong>{catalog?.revision ?? '—'}</strong>
              </div>
              <button
                className="ts-button ts-button--secondary"
                type="button"
                onClick={load}
                disabled={busy}
              >
                <RefreshCcw size={14} className={busy ? 'spin' : ''} />
                Làm mới
              </button>
            </div>

            {busy && !catalog ? (
              <div className="ts-manager-empty" role="status">
                <RefreshCcw className="spin" size={22} />
                <strong>Đang kiểm tra catalog</strong>
              </div>
            ) : rows.length ? (
              <div className="ts-catalog-table-wrap">
                <table className="ts-catalog-table">
                  <thead>
                    <tr>
                      <th>Pack</th>
                      <th>Version</th>
                      <th>Report</th>
                      <th>Trạng thái</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={`${row.packId}:${row.version}`}>
                        <td>
                          <strong>{row.displayName || row.packId}</strong>
                          <code>{row.packId}</code>
                        </td>
                        <td>v{row.version}</td>
                        <td>{row.reportType}</td>
                        <td className="ts-catalog-version-actions">
                          <span
                            className={`ts-catalog-version-state ${row.active ? 'active' : ''}`}
                          >
                            {row.active ? 'Đang chọn' : 'Đã cài'}
                          </span>
                          {!row.active && (
                            <button
                              type="button"
                              onClick={() =>
                                setPendingVersion({ ...row, action: versionAction(row) })
                              }
                              disabled={busy}
                            >
                              {versionAction(row) === 'rollback' ? 'Rollback' : 'Kích hoạt'}
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="ts-manager-empty">
                <Database size={23} />
                <strong>Catalog chưa có Template Pack</strong>
                <span>Pack chỉ xuất hiện sau workflow kiểm thử và phát hành.</span>
              </div>
            )}
          </section>

          <aside className="ts-catalog-health" aria-label="Tình trạng catalog">
            <div className="ts-catalog-health-title">
              {recovery?.canRecover ? <ShieldAlert size={18} /> : <ShieldCheck size={18} />}
              <div>
                <strong>{recovery?.canRecover ? 'Cần khôi phục' : 'Trạng thái lưu trữ'}</strong>
                <span>Legacy Renderer không thay đổi</span>
              </div>
            </div>
            <dl>
              <div>
                <dt>Catalog chính</dt>
                <dd className={recovery?.primary?.valid ? 'valid' : 'invalid'}>
                  {healthLabel(recovery?.primary)}
                </dd>
              </div>
              <div>
                <dt>Checkpoint</dt>
                <dd className={recovery?.checkpoint?.valid ? 'valid' : 'invalid'}>
                  {healthLabel(recovery?.checkpoint)}
                </dd>
              </div>
              <div>
                <dt>Checkpoint rev.</dt>
                <dd>{recovery?.checkpoint?.revision ?? '—'}</dd>
              </div>
            </dl>

            {recovery?.canRecover && !confirmRecovery && (
              <button
                className="ts-button ts-button--danger"
                type="button"
                onClick={() => setConfirmRecovery(true)}
                disabled={busy}
              >
                Khôi phục checkpoint
              </button>
            )}
            {confirmRecovery && (
              <div className="ts-manager-confirm" role="alert">
                <strong>Khôi phục catalog từ checkpoint?</strong>
                <span>
                  Chỉ áp dụng checkpoint vừa được backend kiểm tra; thay đổi mới hơn sẽ bị từ chối.
                </span>
                <div>
                  <button
                    className="ts-button ts-button--secondary"
                    type="button"
                    onClick={() => setConfirmRecovery(false)}
                    disabled={busy}
                  >
                    Hủy
                  </button>
                  <button
                    className="ts-button ts-button--danger"
                    type="button"
                    onClick={recover}
                    disabled={busy}
                  >
                    {status === 'recovering' ? 'Đang khôi phục…' : 'Xác nhận'}
                  </button>
                </div>
              </div>
            )}
            {pendingVersion && (
              <div className="ts-manager-confirm" role="alert">
                <strong>
                  {pendingVersion.action === 'rollback' ? 'Rollback' : 'Kích hoạt'} v
                  {pendingVersion.version}?
                </strong>
                <span>
                  Chỉ thay đổi lựa chọn trong Template Studio; không thay template Generate.
                </span>
                <div>
                  <button
                    className="ts-button ts-button--secondary"
                    type="button"
                    onClick={() => setPendingVersion(null)}
                    disabled={busy}
                  >
                    Hủy
                  </button>
                  <button
                    className="ts-button ts-button--primary"
                    type="button"
                    onClick={selectVersion}
                    disabled={busy}
                  >
                    {status === 'selecting' ? 'Đang cập nhật…' : 'Xác nhận'}
                  </button>
                </div>
              </div>
            )}
          </aside>
        </div>
      </section>
    </div>
  );
}

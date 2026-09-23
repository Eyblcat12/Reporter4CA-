import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  Check,
  Download,
  FileCheck2,
  FileUp,
  LoaderCircle,
  Play,
  RefreshCcw,
  ShieldCheck,
  X,
} from 'lucide-react';
import { downloadValidationArtifact, readValidationFixture } from './validationFixture';

function shortHash(value) {
  return value ? `${value.slice(0, 10)}…${value.slice(-6)}` : '—';
}

function runLabel(run) {
  if (run.stale) return 'Đã cũ';
  if (run.baselineRunId) {
    return run.validation?.readyForVisualReview ? 'Lượt xác minh đạt' : 'Lượt xác minh lỗi';
  }
  return run.baselineApproval ? 'Baseline đã duyệt' : 'Chờ duyệt baseline';
}

export default function ValidationDialog({
  workspace,
  onDismiss,
  onListRuns,
  onCreateRun,
  onDownloadArtifact,
  onApproveBaseline,
  onPublish,
  onLoadCatalog,
  onStageChange,
}) {
  const [history, setHistory] = useState({ items: [], total: 0, skippedCorrupt: 0 });
  const [catalog, setCatalog] = useState(null);
  const [fixture, setFixture] = useState(null);
  const [fixtureId, setFixtureId] = useState('');
  const [reviewer, setReviewer] = useState('');
  const [downloadedRuns, setDownloadedRuns] = useState(() => new Set());
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState(null);
  const [published, setPublished] = useState(null);
  const dialogRef = useRef(null);
  const titleRef = useRef(null);
  const fileRef = useRef(null);

  const runs = history.items || [];
  const usableRuns = runs.filter((run) => !run.stale);
  const approvedBaseline = usableRuns.find((run) => !run.baselineRunId && run.baselineApproval);
  const baselineCandidate =
    approvedBaseline || usableRuns.find((run) => !run.baselineRunId) || null;
  const verifiedRun = usableRuns.find(
    (run) => run.baselineRunId === approvedBaseline?.runId && run.validation?.readyForVisualReview,
  );
  const installedVersion = catalog?.packs?.[workspace.profileId]?.versions?.[workspace.version];
  const currentRun = verifiedRun || baselineCandidate;
  const completedStep =
    installedVersion || published ? 3 : verifiedRun ? 2 : approvedBaseline ? 1 : 0;
  useEffect(() => {
    onStageChange?.(completedStep >= 2 ? 4 : 3);
  }, [completedStep, onStageChange]);
  const issues = useMemo(
    () =>
      (currentRun?.validation?.issues || []).filter(
        (issue) => !(issue.code === 'structural.baseline_missing' && !currentRun.baselineRunId),
      ),
    [currentRun],
  );

  async function load() {
    setStatus('loading');
    setError(null);
    const [runsResult, catalogResult] = await Promise.allSettled([
      onListRuns(workspace.workspaceId),
      onLoadCatalog(),
    ]);
    if (runsResult.status === 'fulfilled') setHistory(runsResult.value);
    if (catalogResult.status === 'fulfilled') setCatalog(catalogResult.value);
    const failure =
      runsResult.status === 'rejected'
        ? runsResult.reason
        : catalogResult.status === 'rejected'
          ? catalogResult.reason
          : null;
    setError(failure);
    setStatus('ready');
  }

  useEffect(() => {
    titleRef.current?.focus();
    load();
  }, [workspace.workspaceId]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleKeyDown(event) {
    if (event.key === 'Escape' && status !== 'working') {
      onDismiss();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = [
      ...dialogRef.current.querySelectorAll(
        'button:not(:disabled), input:not(:disabled), [tabindex="0"]',
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
  }

  async function run(task) {
    setStatus('working');
    setError(null);
    try {
      await task();
      await load();
    } catch (operationError) {
      if (operationError.conflict) await load();
      setError(operationError);
      setStatus('ready');
    }
  }

  async function chooseFixture(event) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setError(null);
    try {
      const parsed = await readValidationFixture(file);
      setFixture(parsed);
      setFixtureId(
        approvedBaseline?.validation?.fixtureId ||
          file.name.replace(/\.(json|csv)$/i, '').slice(0, 128),
      );
    } catch (fixtureError) {
      setFixture(null);
      setError(fixtureError);
    }
  }

  async function createRun() {
    const baselineRunId = approvedBaseline?.runId || '';
    await run(() =>
      onCreateRun(workspace.workspaceId, {
        rows: fixture.rows,
        fixtureId: fixtureId.trim(),
        expectedWorkspaceRevision: workspace.revision,
        baselineRunId,
        metadata: fixture.metadata,
      }),
    );
  }

  async function downloadRun(runRecord) {
    setStatus('working');
    setError(null);
    try {
      const artifact = await onDownloadArtifact(workspace.workspaceId, runRecord.runId);
      if (
        artifact.artifactSha256 &&
        artifact.artifactSha256 !== runRecord.validation.artifactSha256
      ) {
        throw new Error('Checksum artifact tải về không khớp validation run.');
      }
      downloadValidationArtifact(artifact);
      setDownloadedRuns((current) => new Set(current).add(runRecord.runId));
    } catch (operationError) {
      setError(operationError);
    } finally {
      setStatus('ready');
    }
  }

  async function approveBaseline() {
    await run(() =>
      onApproveBaseline(workspace.workspaceId, baselineCandidate.runId, {
        expectedWorkspaceRevision: workspace.revision,
        reviewer: reviewer.trim(),
        artifactSha256: baselineCandidate.validation.artifactSha256,
      }),
    );
  }

  async function publishRun() {
    await run(async () => {
      const result = await onPublish(workspace.workspaceId, verifiedRun.runId, {
        expectedWorkspaceRevision: workspace.revision,
        expectedCatalogRevision: catalog.revision,
        reviewer: reviewer.trim(),
        artifactSha256: verifiedRun.validation.artifactSha256,
      });
      setPublished(result);
    });
  }

  const busy = status === 'loading' || status === 'working';
  const mappingReady = workspace.status === 'mapping_complete';
  const canCreate = Boolean(fixture && fixtureId.trim() && mappingReady && !busy);
  const canApprove = Boolean(
    baselineCandidate &&
    downloadedRuns.has(baselineCandidate.runId) &&
    reviewer.trim() &&
    baselineCandidate.validation?.fixturePassed &&
    baselineCandidate.validation?.integrityPassed &&
    !busy,
  );
  const canPublish = Boolean(
    verifiedRun && downloadedRuns.has(verifiedRun.runId) && reviewer.trim() && catalog && !busy,
  );

  return (
    <div className="ts-manager-backdrop" role="presentation">
      <section
        className="ts-validation"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ts-validation-title"
        ref={dialogRef}
        onKeyDown={handleKeyDown}
      >
        <header className="ts-manager-head">
          <div>
            <h1 id="ts-validation-title" tabIndex="-1" ref={titleRef}>
              Kiểm thử Template Pack
            </h1>
            <p>{workspace.displayName}</p>
          </div>
          <button
            className="ts-icon-button"
            type="button"
            aria-label="Đóng kiểm thử"
            onClick={onDismiss}
            disabled={busy}
          >
            <X size={18} />
          </button>
        </header>

        <div className="ts-validation-steps" aria-label="Tiến độ kiểm thử">
          {['Baseline', 'Xác minh', 'Phát hành'].map((step, index) => (
            <div
              key={step}
              className={`${index < completedStep ? 'done' : ''} ${index === completedStep ? 'current' : ''}`}
            >
              <span>{index < completedStep ? <Check size={12} /> : index + 1}</span>
              {step}
            </div>
          ))}
        </div>

        {error && (
          <div className="ts-manager-error" role="alert">
            <strong>{error.conflict ? 'Dữ liệu đã thay đổi' : 'Thao tác chưa hoàn thành'}</strong>
            <span>{error.message}</span>
            <button type="button" onClick={() => setError(null)}>
              Đóng
            </button>
          </div>
        )}

        <div className="ts-validation-body">
          <main className="ts-validation-main">
            {!mappingReady ? (
              <div className="ts-validation-blocked">
                <AlertTriangle size={20} />
                <div>
                  <strong>Mapping chưa đạt 100%</strong>
                  <span>Hoàn thành các semantic bắt buộc trước khi tạo baseline.</span>
                </div>
              </div>
            ) : installedVersion || published ? (
              <div className="ts-validation-complete">
                <ShieldCheck size={30} />
                <h2>Template Pack đã được phát hành</h2>
                <p>Version v{workspace.version} đã sẵn sàng sử dụng.</p>
                <span>Quay lại Reporter Pro → Configure → Template và chọn phiên bản này.</span>
              </div>
            ) : !baselineCandidate ? (
              <section className="ts-validation-task">
                <div className="ts-validation-task-head">
                  <span>Bước 1</span>
                  <h2>Tạo baseline cấu trúc</h2>
                </div>
                <FixturePicker
                  fixture={fixture}
                  fixtureId={fixtureId}
                  fileRef={fileRef}
                  busy={busy}
                  onChoose={chooseFixture}
                  onFixtureId={setFixtureId}
                />
                <button
                  className="ts-button ts-button--primary"
                  type="button"
                  disabled={!canCreate}
                  onClick={createRun}
                >
                  {busy ? <LoaderCircle className="spin" size={15} /> : <Play size={15} />}
                  {busy ? 'Đang tạo baseline…' : 'Tạo baseline'}
                </button>
              </section>
            ) : !approvedBaseline ? (
              <ReviewTask
                step="Bước 1"
                title="Duyệt baseline"
                run={baselineCandidate}
                issues={issues}
                reviewer={reviewer}
                busy={busy}
                downloaded={downloadedRuns.has(baselineCandidate.runId)}
                canConfirm={canApprove}
                actionLabel="Duyệt baseline"
                onReviewer={setReviewer}
                onDownload={() => downloadRun(baselineCandidate)}
                onConfirm={approveBaseline}
              />
            ) : !verifiedRun ? (
              <section className="ts-validation-task">
                <div className="ts-validation-task-head">
                  <span>Bước 2</span>
                  <h2>Chạy lượt xác minh</h2>
                </div>
                <div className="ts-validation-baseline-ref">
                  <FileCheck2 size={16} />
                  <div>
                    <strong>Baseline đã duyệt</strong>
                    <code>{shortHash(approvedBaseline.validation.artifactSha256)}</code>
                  </div>
                </div>
                <FixturePicker
                  fixture={fixture}
                  fixtureId={approvedBaseline.validation.fixtureId}
                  fileRef={fileRef}
                  busy={busy}
                  lockedId
                  onChoose={chooseFixture}
                  onFixtureId={setFixtureId}
                />
                <button
                  className="ts-button ts-button--primary"
                  type="button"
                  disabled={!canCreate}
                  onClick={createRun}
                >
                  {busy ? <LoaderCircle className="spin" size={15} /> : <Play size={15} />}
                  {busy ? 'Đang xác minh…' : 'Chạy lượt xác minh'}
                </button>
              </section>
            ) : (
              <ReviewTask
                step="Bước 3"
                title="Duyệt và phát hành"
                run={verifiedRun}
                issues={issues}
                reviewer={reviewer}
                busy={busy}
                downloaded={downloadedRuns.has(verifiedRun.runId)}
                canConfirm={canPublish}
                actionLabel="Phát hành vào Catalog"
                onReviewer={setReviewer}
                onDownload={() => downloadRun(verifiedRun)}
                onConfirm={publishRun}
              />
            )}
          </main>

          <aside className="ts-validation-history" aria-label="Lịch sử kiểm thử">
            <div className="ts-validation-history-head">
              <strong>Lịch sử</strong>
              <button type="button" aria-label="Tải lại lịch sử" onClick={load} disabled={busy}>
                <RefreshCcw size={14} className={busy ? 'spin' : ''} />
              </button>
            </div>
            {history.skippedCorrupt > 0 && (
              <div className="ts-validation-history-warning">
                {history.skippedCorrupt} record hỏng đã được cô lập.
              </div>
            )}
            {history.hasMore && (
              <div className="ts-validation-history-warning">
                Đang hiển thị 100/{history.total} run mới nhất.
              </div>
            )}
            <ol>
              {runs.map((run) => (
                <li key={run.runId} className={run.stale ? 'stale' : ''}>
                  <span>{runLabel(run)}</span>
                  <code>{shortHash(run.runId)}</code>
                  <time>{new Date(run.createdAt).toLocaleString('vi-VN')}</time>
                </li>
              ))}
            </ol>
            {!runs.length && status !== 'loading' && (
              <div className="ts-validation-history-empty">Chưa có validation run.</div>
            )}
          </aside>
        </div>
      </section>
    </div>
  );
}

function FixturePicker({
  fixture,
  fixtureId,
  fileRef,
  busy,
  lockedId = false,
  onChoose,
  onFixtureId,
}) {
  return (
    <div className="ts-fixture-picker">
      <input
        ref={fileRef}
        type="file"
        accept=".json,.csv,application/json,text/csv"
        hidden
        onChange={onChoose}
      />
      <button
        className="ts-fixture-file"
        type="button"
        onClick={() => fileRef.current?.click()}
        disabled={busy}
      >
        <FileUp size={18} />
        <span>
          <strong>{fixture?.filename || 'Chọn fixture JSON / Tracking CSV'}</strong>
          <small>
            {fixture ? `${fixture.rows.length.toLocaleString('vi-VN')} dòng` : 'Tối đa 30 MiB'}
          </small>
        </span>
      </button>
      <label>
        Fixture ID
        <input
          value={fixtureId}
          maxLength="128"
          required
          disabled={lockedId || busy}
          onChange={(event) => onFixtureId(event.target.value)}
        />
      </label>
    </div>
  );
}

function ReviewTask({
  step,
  title,
  run,
  issues,
  reviewer,
  busy,
  downloaded,
  canConfirm,
  actionLabel,
  onReviewer,
  onDownload,
  onConfirm,
}) {
  return (
    <section className="ts-validation-task">
      <div className="ts-validation-task-head">
        <span>{step}</span>
        <h2>{title}</h2>
      </div>
      <div className="ts-validation-evidence">
        <div>
          <span>Fixture</span>
          <strong>{run.validation.fixturePassed ? 'Đạt' : 'Lỗi'}</strong>
        </div>
        <div>
          <span>Integrity</span>
          <strong>{run.validation.integrityPassed ? 'Đạt' : 'Lỗi'}</strong>
        </div>
        <div>
          <span>Structure</span>
          <strong>
            {run.baselineRunId ? (run.validation.structuralPassed ? 'Khớp' : 'Lệch') : 'Baseline'}
          </strong>
        </div>
      </div>
      {issues.length > 0 && (
        <div className="ts-validation-issues" role="alert">
          <AlertTriangle size={16} />
          <div>
            <strong>{issues.length} vấn đề cần xử lý</strong>
            <ul>
              {issues.slice(0, 5).map((issue) => (
                <li key={`${issue.code}:${issue.semantic}:${issue.path}`}>
                  {issue.semantic ? `${issue.semantic}: ` : ''}
                  {issue.message}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
      <div className="ts-validation-artifact">
        <div>
          <span>Artifact SHA-256</span>
          <code>{shortHash(run.validation.artifactSha256)}</code>
        </div>
        <button
          className="ts-button ts-button--secondary"
          type="button"
          onClick={onDownload}
          disabled={busy}
        >
          <Download size={14} />
          {downloaded ? 'Tải lại DOCX' : 'Tải DOCX để duyệt'}
        </button>
      </div>
      <label className="ts-validation-reviewer">
        Người duyệt
        <input
          value={reviewer}
          maxLength="128"
          disabled={busy}
          placeholder="Tên hoặc email"
          onChange={(event) => onReviewer(event.target.value)}
        />
      </label>
      <button
        className="ts-button ts-button--primary"
        type="button"
        onClick={onConfirm}
        disabled={!canConfirm || issues.length > 0}
      >
        <Check size={15} />
        {actionLabel}
      </button>
      {!downloaded && (
        <small className="ts-validation-gate">Phải tải đúng artifact trước khi xác nhận.</small>
      )}
    </section>
  );
}

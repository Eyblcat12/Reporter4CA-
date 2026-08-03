import { useRef, useState } from 'react';
import {
  CheckCircle2,
  Download,
  FileArchive,
  LoaderCircle,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Upload,
} from 'lucide-react';
import { useReporterContext } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import './WorkspaceBackup.css';

export default function WorkspaceBackup() {
  const {
    downloadWorkspaceBackup,
    previewWorkspaceRestore,
    restoreWorkspaceBackup,
  } = useReporterContext();
  const { t } = useI18n();
  const [status, setStatus] = useState({ state: 'idle', detail: '' });
  const [restoreStatus, setRestoreStatus] = useState({ state: 'idle', detail: '' });
  const [restoreFile, setRestoreFile] = useState(null);
  const [restorePreview, setRestorePreview] = useState(null);
  const inputRef = useRef(null);

  const download = async () => {
    setStatus({ state: 'loading', detail: '' });
    try {
      const result = await downloadWorkspaceBackup();
      const size = `${(result.size / 1024 / 1024).toFixed(1)} MB`;
      setStatus({ state: 'success', detail: `${result.filename} · ${size}` });
    } catch (error) {
      setStatus({ state: 'error', detail: error.message });
    }
  };

  const selectRestore = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setRestoreFile(file);
    setRestorePreview(null);
    setRestoreStatus({ state: 'loading', detail: t('backup.restoreChecking') });
    try {
      const preview = await previewWorkspaceRestore(file);
      setRestorePreview(preview);
      setRestoreStatus({ state: 'success', detail: t('backup.restoreValid') });
    } catch (error) {
      setRestoreFile(null);
      setRestoreStatus({ state: 'error', detail: error.message });
    }
  };

  const restore = async () => {
    if (!restoreFile || !restorePreview) return;
    if (!window.confirm(t('backup.restoreConfirm'))) return;
    setRestoreStatus({ state: 'loading', detail: t('backup.restoring') });
    try {
      await restoreWorkspaceBackup(restoreFile, restorePreview.confirmationToken);
      setRestoreStatus({ state: 'restored', detail: t('backup.restoreSuccess') });
    } catch (error) {
      setRestoreStatus({ state: 'error', detail: error.message });
    }
  };

  return (
    <div className="workspace-backup">
      <div className="workspace-backup__summary">
        <div className="workspace-backup__shield" aria-hidden="true">
          <ShieldCheck size={24} />
        </div>
        <div>
          <strong>{t('backup.snapshot')}</strong>
          <p>{t('backup.contents')}</p>
        </div>
      </div>

      <div className="workspace-backup__warning">{t('backup.warning')}</div>

      <button
        type="button"
        className="workspace-backup__button"
        onClick={download}
        disabled={status.state === 'loading'}
      >
        {status.state === 'loading' ? (
          <LoaderCircle className="workspace-backup__spinner" size={17} />
        ) : (
          <Download size={17} />
        )}
        {status.state === 'loading' ? t('backup.creating') : t('backup.download')}
      </button>

      {status.detail && (
        <div className={`workspace-backup__status workspace-backup__status--${status.state}`}>
          {status.state === 'success' && <CheckCircle2 size={15} />}
          <span>{status.detail}</span>
        </div>
      )}

      <div className="workspace-backup__divider" />

      <div className="workspace-backup__summary">
        <div className="workspace-backup__shield" aria-hidden="true">
          <RotateCcw size={23} />
        </div>
        <div>
          <strong>{t('backup.restoreTitle')}</strong>
          <p>{t('backup.restoreDescription')}</p>
        </div>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".zip,application/zip"
        hidden
        onChange={selectRestore}
      />
      <button
        type="button"
        className="workspace-backup__button workspace-backup__button--secondary"
        onClick={() => inputRef.current?.click()}
        disabled={restoreStatus.state === 'loading'}
      >
        {restoreStatus.state === 'loading' && !restorePreview ? (
          <LoaderCircle className="workspace-backup__spinner" size={17} />
        ) : (
          <Upload size={17} />
        )}
        {t('backup.restoreSelect')}
      </button>

      {restorePreview && (
        <div className="workspace-backup__preview">
          <div className="workspace-backup__preview-title">
            <FileArchive size={17} />
            <strong>{restoreFile?.name}</strong>
          </div>
          <dl>
            <div><dt>{t('backup.restoreCreated')}</dt><dd>{new Date(restorePreview.archive.createdAt).toLocaleString()}</dd></div>
            <div><dt>Presets</dt><dd>{restorePreview.database.records.presets}</dd></div>
            <div><dt>History</dt><dd>{restorePreview.database.records.report_history}</dd></div>
            <div><dt>Rules</dt><dd>{restorePreview.database.records.detection_rules ?? 0}</dd></div>
            <div><dt>Templates</dt><dd>{restorePreview.templateCount}</dd></div>
          </dl>
          {restorePreview.warnings?.map((warning) => (
            <p className="workspace-backup__preview-warning" key={warning}>{warning}</p>
          ))}
          <button
            type="button"
            className="workspace-backup__button"
            onClick={restore}
            disabled={restoreStatus.state === 'loading'}
          >
            {restoreStatus.state === 'loading' ? (
              <LoaderCircle className="workspace-backup__spinner" size={17} />
            ) : (
              <RotateCcw size={17} />
            )}
            {t('backup.restoreApply')}
          </button>
        </div>
      )}

      {restoreStatus.detail && (
        <div className={`workspace-backup__status workspace-backup__status--${restoreStatus.state}`}>
          {(restoreStatus.state === 'success' || restoreStatus.state === 'restored') && <CheckCircle2 size={15} />}
          <span>{restoreStatus.detail}</span>
          {restoreStatus.state === 'restored' && (
            <button type="button" onClick={() => window.location.reload()}>
              <RefreshCw size={14} /> {t('backup.reload')}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

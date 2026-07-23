import { useState } from 'react';
import { CheckCircle2, Download, LoaderCircle, ShieldCheck } from 'lucide-react';
import { useReporterContext } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import './WorkspaceBackup.css';

export default function WorkspaceBackup() {
  const { downloadWorkspaceBackup } = useReporterContext();
  const { t } = useI18n();
  const [status, setStatus] = useState({ state: 'idle', detail: '' });

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
    </div>
  );
}

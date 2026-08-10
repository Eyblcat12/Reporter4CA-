import { useEffect, useState } from 'react';
import { CheckCircle2, Download, FileClock, Loader2, X, XCircle } from 'lucide-react';
import { useReporterContext } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import './ReportJobPanel.css';

const RUNNING = new Set(['queued', 'running']);

export default function ReportJobPanel() {
  const { activeReportJob: job, cancelReportJob, downloadReportJob } = useReporterContext();
  const { t } = useI18n();
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (job?.id) setDismissed(false);
  }, [job?.id]);

  useEffect(() => {
    if (!RUNNING.has(job?.status)) return undefined;
    const warnBeforeExit = (event) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warnBeforeExit);
    return () => window.removeEventListener('beforeunload', warnBeforeExit);
  }, [job?.status]);

  if (!job) return null;
  if (dismissed) {
    return (
      <button className="report-job-fab" type="button" onClick={() => setDismissed(false)}>
        {RUNNING.has(job.status) ? (
          <Loader2 className="report-job-spin" size={17} />
        ) : (
          <FileClock size={17} />
        )}
        <span>{job.progress || 0}%</span>
      </button>
    );
  }

  const completed = job.status === 'completed';
  const failed = job.status === 'failed' || job.status === 'cancelled';
  return (
    <aside className="report-job-panel" aria-label={t('jobs.title')}>
      <div className="report-job-panel__head">
        <div className={`report-job-panel__icon report-job-panel__icon--${job.status}`}>
          {completed ? (
            <CheckCircle2 size={18} />
          ) : failed ? (
            <XCircle size={18} />
          ) : (
            <Loader2 className="report-job-spin" size={18} />
          )}
        </div>
        <div>
          <strong>{job.filename || t('jobs.generating')}</strong>
          <span>{job.message || t('jobs.queued')}</span>
        </div>
        <button type="button" onClick={() => setDismissed(true)} aria-label={t('common.close')}>
          <X size={15} />
        </button>
      </div>
      <div className="report-job-panel__progress-row">
        <span>{t(`jobs.phase.${job.phase}`)}</span>
        <b>{job.progress || 0}%</b>
      </div>
      <div className="report-job-panel__track">
        <i style={{ width: `${job.progress || 0}%` }} />
      </div>
      <div className="report-job-panel__actions">
        <small>
          {RUNNING.has(job.status) ? t('jobs.backgroundHint') : t(`jobs.status.${job.status}`)}
        </small>
        {RUNNING.has(job.status) && (
          <button
            className="btn btn--ghost btn--sm report-job-panel__cancel"
            type="button"
            onClick={() => cancelReportJob(job.id)}
          >
            {t('jobs.cancel')}
          </button>
        )}
        {completed && (
          <button
            className="btn btn--primary btn--sm"
            type="button"
            onClick={() => downloadReportJob(job)}
          >
            <Download size={13} />
            {t('jobs.downloadAgain')}
          </button>
        )}
      </div>
    </aside>
  );
}

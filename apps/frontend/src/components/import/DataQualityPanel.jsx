import { AlertTriangle, CheckCircle2, Copy, ShieldAlert, WandSparkles } from 'lucide-react';
import { useI18n } from '../../i18n';
import './DataQualityPanel.css';

export default function DataQualityPanel({
  quality,
  activeFilter,
  onFilter,
  onIssue,
  onTrimValues,
  onFillResult,
}) {
  const { t } = useI18n();
  const summary = quality?.summary;
  if (!summary) return null;

  const cards = [
    { id: 'all', label: t('quality.validRows'), value: summary.validRows, icon: CheckCircle2, tone: 'success' },
    { id: 'errors', label: t('quality.errors'), value: summary.errorRows, icon: ShieldAlert, tone: 'danger' },
    { id: 'warnings', label: t('quality.warnings'), value: summary.warningRows, icon: AlertTriangle, tone: 'warning' },
    { id: 'duplicate_hostname', label: t('quality.duplicates'), value: summary.duplicateHostnames, icon: Copy },
    { id: 'invalid_ip', label: t('quality.invalidIps'), value: summary.invalidIps },
    { id: 'missing_os', label: t('quality.missingOs'), value: summary.missingOs },
    { id: 'missing_result', label: t('quality.missingResult'), value: summary.missingResult },
  ];

  return (
    <section className="quality-panel" aria-label={t('quality.title')}>
      <div className="quality-panel__head">
        <div>
          <strong>{t('quality.title')}</strong>
          <span>
            {quality.valid ? t('quality.ready') : t('quality.blocked')}
            {' · '}{t('quality.serverClient')} {summary.servers || 0}:{summary.clients || 0}
          </span>
        </div>
        <div className="quality-panel__actions">
          <button className="btn btn--ghost btn--sm" type="button" onClick={onTrimValues}>
            <WandSparkles size={13} /> {t('quality.trim')}
          </button>
          {summary.missingResult > 0 && (
            <button className="btn btn--ghost btn--sm" type="button" onClick={onFillResult}>
              {t('quality.fillResult')}
            </button>
          )}
        </div>
      </div>
      <div className="quality-panel__cards">
        {cards.map(({ id, label, value, icon: Icon, tone = '' }) => (
          <button
            key={id}
            className={`quality-card quality-card--${tone} ${activeFilter === id ? 'quality-card--active' : ''}`}
            type="button"
            onClick={() => onFilter(id)}
            aria-pressed={activeFilter === id}
          >
            <span>{Icon && <Icon size={13} />}{label}</span>
            <strong>{value || 0}</strong>
          </button>
        ))}
      </div>
      {quality.issues?.length > 0 && (
        <div className="quality-panel__issues">
          {quality.issues.slice(0, 5).map((issue, index) => (
            <button
              key={`${issue.row}-${issue.code}-${index}`}
              type="button"
              onClick={() => onIssue(issue)}
            >
              <span className={`quality-panel__dot quality-panel__dot--${issue.level}`} />
              <b>{t('quality.row')} {issue.row}</b>
              <span>{issue.message}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

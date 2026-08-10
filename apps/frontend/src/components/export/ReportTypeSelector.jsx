/* ═══════════════════════════════════════════════════════════
   ReportTypeSelector — Premium radio card grid
   ═══════════════════════════════════════════════════════════ */
import { motion } from 'framer-motion';
import { FileStack, Server, Monitor, BarChart3, Code, ShieldAlert } from 'lucide-react';
import { useReporterContext } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import './ReportTypeSelector.css';

const TYPES = [
  { id: 'full', icon: FileStack, titleKey: 'export.full', descKey: 'export.full.desc' },
  {
    id: 'server_only',
    icon: Server,
    titleKey: 'export.serverOnly',
    descKey: 'export.serverOnly.desc',
  },
  {
    id: 'client_only',
    icon: Monitor,
    titleKey: 'export.clientOnly',
    descKey: 'export.clientOnly.desc',
  },
  { id: 'summary', icon: BarChart3, titleKey: 'export.summary', descKey: 'export.summary.desc' },
  { id: 'technical', icon: Code, titleKey: 'export.technical', descKey: 'export.technical.desc' },
  { id: 'incident_response', icon: ShieldAlert, titleKey: 'export.ir', descKey: 'export.ir.desc' },
];

export default function ReportTypeSelector() {
  const { reportSettings, setReportSettings, templates } = useReporterContext();
  const { t } = useI18n();
  const selected = reportSettings.reportType || 'full';

  const handleSelect = (id) => {
    const currentTemplate = (templates || []).find(
      (tpl) => tpl.path === reportSettings.templatePath,
    );
    const keepCurrentTemplate = currentTemplate?.reportType === id;
    const categoryDefault = (templates || []).find((tpl) => tpl.reportType === id && tpl.isDefault);
    setReportSettings({
      ...reportSettings,
      reportType: id,
      templatePath: keepCurrentTemplate ? reportSettings.templatePath : categoryDefault?.path || '',
    });
  };

  return (
    <div className="rts">
      <h3 className="rts__title">{t('export.reportType')}</h3>

      <div className="rts__grid">
        {TYPES.map((type, idx) => {
          const Icon = type.icon;
          const isSelected = selected === type.id;

          return (
            <motion.button
              key={type.id}
              type="button"
              className={`rts__card ${isSelected ? 'rts__card--selected' : ''}`}
              onClick={() => handleSelect(type.id)}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.04, duration: 0.3 }}
              whileHover={{ scale: 1.015 }}
              whileTap={{ scale: 0.985 }}
            >
              <div className="rts__card-icon">
                <Icon size={18} />
              </div>

              <div className="rts__card-text">
                <span className="rts__card-title">{t(type.titleKey)}</span>
                <span className="rts__card-desc">{t(type.descKey)}</span>
              </div>

              <div className={`rts__radio ${isSelected ? 'rts__radio--active' : ''}`}>
                {isSelected && (
                  <motion.div
                    className="rts__radio-dot"
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: 'spring', stiffness: 500, damping: 25 }}
                  />
                )}
              </div>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   GenerateButton — Premium CTA with preview & save-as-template
   ═══════════════════════════════════════════════════════════ */
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Zap, Loader2, Eye, Save, X } from 'lucide-react';
import { useReporterContext } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import './GenerateButton.css';

export default function GenerateButton() {
  const {
    generateReport, previewDocx, saveReportAsTemplate,
    rows, loading, lastReportId, dataQuality, activeReportJob,
  } = useReporterContext();
  const { t } = useI18n();
  const [showSaveForm, setShowSaveForm] = useState(false);
  const [templateName, setTemplateName] = useState('');

  const hasData = rows && rows.length > 0;
  const hasBlockingErrors = dataQuality?.valid === false;
  const jobRunning = ['queued', 'running'].includes(activeReportJob?.status);
  const previewDisabled = !hasData || loading;
  const isDisabled = previewDisabled || hasBlockingErrors || jobRunning;

  const handleGenerate = async () => {
    if (isDisabled) return;
    try {
      await generateReport();
    } catch {
      /* error handled by context */
    }
  };

  const handlePreview = async () => {
    if (isDisabled) return;
    await previewDocx();
  };

  const handleSaveAsTemplate = async () => {
    if (!templateName.trim()) return;
    const ok = await saveReportAsTemplate(templateName.trim());
    if (ok) {
      setShowSaveForm(false);
      setTemplateName('');
    }
  };

  return (
    <div className="gen-btn-group">
      {/* Preview Button */}
      <motion.button
        className="gen-btn gen-btn--preview"
        onClick={handlePreview}
        disabled={previewDisabled}
        whileHover={!previewDisabled ? { scale: 1.01 } : {}}
        whileTap={!previewDisabled ? { scale: 0.99 } : {}}
        transition={{ duration: 0.15 }}
      >
        <span className="gen-btn__icon">
          <Eye size={18} />
        </span>
        <span className="gen-btn__label">
          {t('preview.title') || 'Xem trước'}
        </span>
      </motion.button>

      {/* Generate Button */}
      <motion.button
        className={`gen-btn gen-btn--primary ${loading ? 'gen-btn--loading' : ''}`}
        onClick={handleGenerate}
        disabled={isDisabled}
        whileHover={!isDisabled ? { scale: 1.01, filter: 'brightness(1.08)' } : {}}
        whileTap={!isDisabled ? { scale: 0.99 } : {}}
        transition={{ duration: 0.15 }}
        title={hasBlockingErrors ? t('quality.generateBlocked') : undefined}
      >
        <span className="gen-btn__icon">
          {loading ? (
            <Loader2 size={20} className="gen-btn__spinner" />
          ) : (
            <Zap size={20} />
          )}
        </span>
        <span className="gen-btn__label">
          {loading || jobRunning ? t('jobs.inProgress') : t('export.generate')}
        </span>
      </motion.button>

      {/* Save as Template */}
      <AnimatePresence>
        {lastReportId && !showSaveForm && (
          <motion.button
            className="gen-btn gen-btn--save"
            onClick={() => setShowSaveForm(true)}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
          >
            <span className="gen-btn__icon"><Save size={16} /></span>
            <span className="gen-btn__label">
              {t('preview.saveAsTemplate') || 'Lưu làm template'}
            </span>
          </motion.button>
        )}
      </AnimatePresence>

      {/* Save form */}
      <AnimatePresence>
        {showSaveForm && (
          <motion.div
            className="gen-btn__save-form"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
          >
            <input
              className="gen-btn__save-input"
              type="text"
              placeholder="Tên template..."
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSaveAsTemplate()}
              autoFocus
            />
            <button className="btn btn--primary btn--sm" onClick={handleSaveAsTemplate} disabled={!templateName.trim()}>
              <Save size={14} />
            </button>
            <button className="btn btn--ghost btn--sm" onClick={() => setShowSaveForm(false)}>
              <X size={14} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

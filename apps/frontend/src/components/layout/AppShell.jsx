/* ═══════════════════════════════════════════════════════════
   AppShell — Main layout with sidebar + header + bottom bar
   ═══════════════════════════════════════════════════════════ */
import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowRight, ArrowLeft, Zap } from 'lucide-react';
import { useReporterContext } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import Sidebar from './Sidebar';
import ImportStep from '../import/ImportStep';
import ConfigureStep from '../configure/ConfigureStep';
import ExportStep from '../export/ExportStep';
import DashboardHome from '../shared/DashboardHome';
import './AppShell.css';

const stepVariants = {
  enter: { opacity: 0, y: 16, filter: 'blur(4px)' },
  center: { opacity: 1, y: 0, filter: 'blur(0px)' },
  exit: { opacity: 0, y: -12, filter: 'blur(4px)' },
};

const STEP_KEYS = ['import', 'configure', 'export'];

export default function AppShell() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [homeDismissed, setHomeDismissed] = useState(false);
  const [importEntryTab, setImportEntryTab] = useState('file');
  const { currentStep, setStep, rows } = useReporterContext();
  const { t } = useI18n();

  const showWelcome = currentStep === 1 && (!rows || rows.length === 0) && !homeDismissed;
  const canGoBack = currentStep > 1;
  const canGoNext = currentStep < 3;

  const openImport = (tab = 'file') => {
    setImportEntryTab(tab);
    setHomeDismissed(true);
    setStep(1);
  };

  const renderStep = () => {
    if (showWelcome) return <DashboardHome onOpenImport={openImport} />;
    switch (currentStep) {
      case 1: return <ImportStep initialTab={importEntryTab} />;
      case 2: return <ConfigureStep />;
      case 3: return <ExportStep />;
      default: return <ImportStep />;
    }
  };

  return (
    <div className="app-shell">
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      <main className="app-main">
        {/* ─── Header ─── */}
        <div className="app-main__header">
          <div className="app-main__breadcrumb">
            {/* Step breadcrumb trail */}
            {!showWelcome && STEP_KEYS.map((key, idx) => {
              const stepNum = idx + 1;
              const isActive = currentStep === stepNum;
              const isPast = currentStep > stepNum;
              return (
                <span key={key} className="app-main__crumb-group">
                  {idx > 0 && <span className="app-main__crumb-sep">/</span>}
                  <button
                    className={`app-main__crumb ${isActive ? 'app-main__crumb--active' : ''} ${isPast ? 'app-main__crumb--past' : ''}`}
                    onClick={() => setStep(stepNum)}
                  >
                    {t(`step.${key}`)}
                  </button>
                </span>
              );
            })}
            {showWelcome && (
              <span className="app-main__crumb app-main__crumb--active">
                <Zap size={14} />
                {t('app.subtitle')}
              </span>
            )}
          </div>

          {/* Step counter */}
          {!showWelcome && (
            <div className="app-main__step-counter">
              <span className="app-main__step-num">{currentStep}</span>
              <span className="app-main__step-of">/</span>
              <span className="app-main__step-total">3</span>
            </div>
          )}
        </div>

        {/* ─── Content ─── */}
        <div className="app-main__content">
          <AnimatePresence mode="wait">
            <motion.div
              key={showWelcome ? 'welcome' : currentStep}
              variants={stepVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              className="app-step-container"
            >
              {renderStep()}
            </motion.div>
          </AnimatePresence>
        </div>

        {/* ─── Bottom Navigation Bar ─── */}
        {!showWelcome && (
          <motion.div
            className="app-main__bottombar"
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            <button
              className="app-main__nav-btn app-main__nav-btn--back"
              onClick={() => setStep(currentStep - 1)}
              disabled={!canGoBack}
            >
              <ArrowLeft size={16} />
              <span>{t('common.back')}</span>
              <span className="kbd">Ctrl</span>
              <span className="kbd">{currentStep - 1 || '—'}</span>
            </button>

            <div className="app-main__nav-dots">
              {[1, 2, 3].map((s) => (
                <button
                  key={s}
                  className={`app-main__nav-dot ${currentStep === s ? 'app-main__nav-dot--active' : ''} ${currentStep > s ? 'app-main__nav-dot--done' : ''}`}
                  onClick={() => setStep(s)}
                />
              ))}
            </div>

            <button
              className="app-main__nav-btn app-main__nav-btn--next"
              onClick={() => setStep(currentStep + 1)}
              disabled={!canGoNext}
            >
              <span>{t('common.next')}</span>
              <span className="kbd">Ctrl</span>
              <span className="kbd">{currentStep + 1 > 3 ? '—' : currentStep + 1}</span>
              <ArrowRight size={16} />
            </button>
          </motion.div>
        )}
      </main>
    </div>
  );
}

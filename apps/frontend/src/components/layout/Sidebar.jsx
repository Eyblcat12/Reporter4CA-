/* ═══════════════════════════════════════════════════════════
   Sidebar — Premium vertical navigation with progress & stats
   Linear/Vercel inspired design
   ═══════════════════════════════════════════════════════════ */
import { useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Zap, Upload, Settings, FileOutput,
  ChevronLeft, ChevronRight,
  Server, Monitor, Layers,
  Search, Plus, BookOpen,
  CheckCircle2
} from 'lucide-react';
import { useReporterContext } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import ThemeToggle from './ThemeToggle';
import LanguageSwitcher from './LanguageSwitcher';
import packageInfo from '../../../package.json';
import './Sidebar.css';

const STEPS = [
  { id: 1, icon: Upload, labelKey: 'step.import', descKey: 'import.dropzone' },
  { id: 2, icon: Settings, labelKey: 'step.configure', descKey: 'configure.subtitle' },
  { id: 3, icon: FileOutput, labelKey: 'step.export', descKey: 'export.reportType' },
];

/* SVG progress circle */
function StepProgress({ step, total, isActive, isCompleted }) {
  const circumference = 2 * Math.PI * 10;
  const progress = isCompleted ? 1 : isActive ? ((step - 1) / total) + 0.33 : 0;
  const offset = circumference * (1 - progress);

  return (
    <svg className="sidebar__progress-ring" viewBox="0 0 28 28" width="28" height="28">
      <circle
        cx="14" cy="14" r="10"
        fill="none"
        stroke="var(--border)"
        strokeWidth="2"
      />
      <motion.circle
        cx="14" cy="14" r="10"
        fill="none"
        stroke={isCompleted ? 'var(--success)' : 'var(--accent)'}
        strokeWidth="2"
        strokeLinecap="round"
        strokeDasharray={circumference}
        animate={{ strokeDashoffset: offset }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        style={{ transformOrigin: 'center', transform: 'rotate(-90deg)' }}
      />
      <text
        x="14" y="14"
        textAnchor="middle"
        dominantBaseline="central"
        className="sidebar__progress-text"
        fill={isCompleted ? 'var(--success)' : isActive ? 'var(--accent)' : 'var(--text-tertiary)'}
        fontSize="9"
        fontWeight="700"
        fontFamily="var(--font-mono)"
      >
        {isCompleted ? '✓' : step}
      </text>
    </svg>
  );
}

/* Mini horizontal bar */
function MiniBar({ value, max, color }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="sidebar__minibar">
      <motion.div
        className="sidebar__minibar-fill"
        style={{ background: color }}
        initial={{ width: 0 }}
        animate={{ width: `${pct}%` }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      />
    </div>
  );
}

export default function Sidebar({ collapsed, onToggle }) {
  const { currentStep, setStep, counts, rows } = useReporterContext();
  const { t } = useI18n();

  const totalAssets = counts.total || 0;

  return (
    <motion.aside
      className={`sidebar ${collapsed ? 'sidebar--collapsed' : ''}`}
      animate={{ width: collapsed ? 68 : 260 }}
      transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
    >
      {/* ─── Logo ─── */}
      <div className="sidebar__logo">
        <div className="sidebar__logo-icon">
          <Zap size={18} />
        </div>
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              className="sidebar__logo-text"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.15 }}
            >
              <span className="sidebar__logo-title">Reporter Pro</span>
              <span className="sidebar__logo-version">v{packageInfo.version}</span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ─── Navigation Steps ─── */}
      <nav className="sidebar__nav">
        <AnimatePresence>
          {!collapsed && (
            <motion.span
              className="sidebar__nav-section-label"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              WORKFLOW
            </motion.span>
          )}
        </AnimatePresence>

        {STEPS.map((step) => {
          const Icon = step.icon;
          const isActive = currentStep === step.id;
          const isCompleted = currentStep > step.id;

          return (
            <button
              key={step.id}
              className={`sidebar__nav-item ${isActive ? 'sidebar__nav-item--active' : ''} ${isCompleted ? 'sidebar__nav-item--completed' : ''}`}
              onClick={() => setStep(step.id)}
              data-tooltip={collapsed ? t(step.labelKey) : undefined}
            >
              {/* Active bar indicator */}
              {isActive && (
                <motion.div
                  className="sidebar__active-bar"
                  layoutId="sidebar-active-bar"
                  transition={{ type: 'spring', stiffness: 400, damping: 28 }}
                />
              )}

              <div className="sidebar__nav-icon">
                {isCompleted ? (
                  <CheckCircle2 size={18} />
                ) : (
                  <Icon size={18} />
                )}
              </div>

              <AnimatePresence>
                {!collapsed && (
                  <motion.div
                    className="sidebar__nav-text"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.1 }}
                  >
                    <span className="sidebar__nav-label">{t(step.labelKey)}</span>
                    <span className="sidebar__nav-desc">{t(step.descKey)}</span>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Step progress ring (collapsed mode) */}
              {collapsed && (
                <div className="sidebar__step-badge">
                  <StepProgress
                    step={step.id}
                    total={STEPS.length}
                    isActive={isActive}
                    isCompleted={isCompleted}
                  />
                </div>
              )}
            </button>
          );
        })}
      </nav>

      {/* ─── Stats ─── */}
      <div className="sidebar__stats">
        <AnimatePresence>
          {!collapsed && (
            <motion.span
              className="sidebar__nav-section-label"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              ASSETS
            </motion.span>
          )}
        </AnimatePresence>

        <div className="sidebar__stat" style={{ '--stat-color': '#60a5fa' }}>
          <Server size={14} />
          <AnimatePresence>
            {!collapsed && (
              <motion.div className="sidebar__stat-info" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <span className="sidebar__stat-label">{t('common.servers')}</span>
                <MiniBar value={counts.servers} max={totalAssets} color="#60a5fa" />
              </motion.div>
            )}
          </AnimatePresence>
          <span className="sidebar__stat-num">
            <motion.span
              key={counts.servers}
              initial={{ y: -8, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 300 }}
            >
              {counts.servers}
            </motion.span>
          </span>
        </div>

        <div className="sidebar__stat" style={{ '--stat-color': '#34d399' }}>
          <Monitor size={14} />
          <AnimatePresence>
            {!collapsed && (
              <motion.div className="sidebar__stat-info" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <span className="sidebar__stat-label">{t('common.clients')}</span>
                <MiniBar value={counts.clients} max={totalAssets} color="#34d399" />
              </motion.div>
            )}
          </AnimatePresence>
          <span className="sidebar__stat-num">
            <motion.span
              key={counts.clients}
              initial={{ y: -8, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 300 }}
            >
              {counts.clients}
            </motion.span>
          </span>
        </div>

        <div className="sidebar__stat sidebar__stat--total" style={{ '--stat-color': '#a78bfa' }}>
          <Layers size={14} />
          <AnimatePresence>
            {!collapsed && (
              <motion.div className="sidebar__stat-info" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <span className="sidebar__stat-label">{t('common.total')}</span>
                <MiniBar value={totalAssets} max={totalAssets} color="#a78bfa" />
              </motion.div>
            )}
          </AnimatePresence>
          <span className="sidebar__stat-num">
            <motion.span
              key={counts.total}
              initial={{ y: -8, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 300 }}
            >
              {counts.total}
            </motion.span>
          </span>
        </div>
      </div>

      {/* ─── Bottom ─── */}
      <div className="sidebar__bottom">
        {/* Command palette hint */}
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              className="sidebar__cmd-hint"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <Search size={12} />
              <span>Search</span>
              <span className="kbd">Ctrl</span>
              <span className="kbd">K</span>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="sidebar__controls">
          <LanguageSwitcher compact={collapsed} />
          <ThemeToggle compact={collapsed} />
        </div>

        <button className="sidebar__collapse-btn" onClick={onToggle}>
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
    </motion.aside>
  );
}

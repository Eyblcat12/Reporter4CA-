/* ═══════════════════════════════════════════════════════════
   PreviewPanel — Tabbed viewer with animated indicator,
   color-coded logs, and animated copy feedback
   ═══════════════════════════════════════════════════════════ */
import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FileText, Code, Terminal, Copy, Check, AlertCircle, CheckCircle, Info } from 'lucide-react';
import { useReporterContext } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import './PreviewPanel.css';

const TABS = [
  { id: 'preview', icon: FileText, labelKey: 'export.preview' },
  { id: 'json', icon: Code, labelKey: 'export.json' },
  { id: 'log', icon: Terminal, labelKey: 'export.log' },
];

function LogEntry({ entry, index }) {
  const isString = typeof entry === 'string';
  const time = isString ? null : entry.time;
  const message = isString ? entry : entry.message;
  const level = isString ? 'info' : (entry.level || 'info');

  const levelIcons = {
    error: <AlertCircle size={12} />,
    success: <CheckCircle size={12} />,
    warning: <AlertCircle size={12} />,
    info: <Info size={12} />,
  };

  return (
    <motion.div
      className={`pp__log-entry pp__log-entry--${level}`}
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.02, duration: 0.2 }}
    >
      <span className="pp__log-icon">{levelIcons[level] || levelIcons.info}</span>
      {time && <span className="pp__log-time">{time}</span>}
      <span className="pp__log-msg">{message}</span>
    </motion.div>
  );
}

export default function PreviewPanel() {
  const [activeTab, setActiveTab] = useState('preview');
  const [copied, setCopied] = useState(false);
  const { previewText, payload, logs } = useReporterContext();
  const { t } = useI18n();
  const tabsRef = useRef({});
  const [indicatorStyle, setIndicatorStyle] = useState({});

  // Animated tab indicator position
  useEffect(() => {
    const el = tabsRef.current[activeTab];
    if (el) {
      setIndicatorStyle({
        left: el.offsetLeft,
        width: el.offsetWidth,
      });
    }
  }, [activeTab]);

  const getContent = () => {
    switch (activeTab) {
      case 'preview':
        return previewText || t('export.noPreview');
      case 'json':
        return payload ? JSON.stringify(payload, null, 2) : '{}';
      default:
        return '';
    }
  };

  const getCopyText = () => {
    switch (activeTab) {
      case 'preview': return previewText || '';
      case 'json': return payload ? JSON.stringify(payload, null, 2) : '{}';
      case 'log': return (logs || []).map((l) => (typeof l === 'string' ? l : `[${l.time}] ${l.message}`)).join('\n');
      default: return '';
    }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(getCopyText());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.error('Copy failed:', e);
    }
  };

  return (
    <div className="pp card-glass-premium">
      {/* Tab Header */}
      <div className="pp__header">
        <div className="pp__tabs">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                ref={(el) => { tabsRef.current[tab.id] = el; }}
                type="button"
                className={`pp__tab ${isActive ? 'pp__tab--active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                <Icon size={14} />
                <span>{t(tab.labelKey)}</span>
                {/* Log count badge */}
                {tab.id === 'log' && (logs || []).length > 0 && (
                  <span className="pp__tab-badge">{logs.length}</span>
                )}
              </button>
            );
          })}
          {/* Animated indicator */}
          <motion.div
            className="pp__tab-slider"
            animate={indicatorStyle}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          />
        </div>

        {/* Copy button with icon morph */}
        <motion.button
          type="button"
          className={`pp__copy-btn ${copied ? 'pp__copy-btn--copied' : ''}`}
          onClick={handleCopy}
          whileTap={{ scale: 0.92 }}
        >
          <AnimatePresence mode="wait">
            {copied ? (
              <motion.span
                key="check"
                initial={{ scale: 0, rotate: -90 }}
                animate={{ scale: 1, rotate: 0 }}
                exit={{ scale: 0 }}
                transition={{ type: 'spring', stiffness: 500, damping: 20 }}
              >
                <Check size={14} />
              </motion.span>
            ) : (
              <motion.span
                key="copy"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                exit={{ scale: 0 }}
              >
                <Copy size={14} />
              </motion.span>
            )}
          </AnimatePresence>
          <span>{copied ? t('export.copied') : t('export.copy')}</span>
        </motion.button>
      </div>

      {/* Tab Content */}
      <div className="pp__content">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
          >
            {activeTab === 'log' ? (
              <div className="pp__log-list">
                {(logs || []).length === 0 ? (
                  <div className="pp__empty">
                    <Terminal size={24} />
                    <span>{t('export.noLogs')}</span>
                  </div>
                ) : (
                  (logs || []).map((entry, idx) => (
                    <LogEntry key={idx} entry={entry} index={idx} />
                  ))
                )}
              </div>
            ) : (
              <pre className="pp__code">
                <code>{getContent()}</code>
              </pre>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

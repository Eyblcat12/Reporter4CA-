/* ═══════════════════════════════════════════════════════════
   RawTextInput — Code-editor style raw text input
   ═══════════════════════════════════════════════════════════ */
import { useState, useRef, useCallback, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Send, Server, Monitor, Columns, LayoutList, Sparkles } from 'lucide-react';
import { useReporterContext } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import './RawTextInput.css';

const PLACEHOLDER = `type,hostname,os,ip
server,SRV-APP-01,Windows Server 2019,10.0.0.10
server,SRV-DB-01,Windows Server 2016,10.0.0.20
client,PC-HR-01,Windows 11,10.0.1.10
client,MAC-DESIGN-01,macOS Sonoma,10.0.1.21`;

const CSV_TEMPLATE = `type,hostname,os,ip
server,SRV-01,Windows Server 2022,10.0.0.1
client,PC-01,Windows 11,10.0.1.1`;

const TSV_TEMPLATE = `type\thostname\tos\tip
server\tSRV-01\tWindows Server 2022\t10.0.0.1
client\tPC-01\tWindows 11\t10.0.1.1`;

export default function RawTextInput() {
  const [text, setText] = useState('');
  const [defaultType, setDefaultType] = useState('client');
  const textareaRef = useRef(null);
  const { normalizeRaw, loading } = useReporterContext();
  const { t } = useI18n();

  const handleNormalize = () => {
    if (text.trim()) {
      normalizeRaw(text, defaultType);
    }
  };

  const insertTemplate = useCallback((template) => {
    setText(template);
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  }, []);

  const lineCount = useMemo(() => {
    if (!text) return 5;
    const count = text.split('\n').length;
    return Math.max(count, 5);
  }, [text]);

  const lineNumbers = useMemo(() => {
    return Array.from({ length: lineCount }, (_, i) => i + 1);
  }, [lineCount]);

  const handleScroll = (e) => {
    const lineNumEl = e.target.previousElementSibling;
    if (lineNumEl) {
      lineNumEl.scrollTop = e.target.scrollTop;
    }
  };

  return (
    <div className="raw-text">
      {/* ─── Top bar: type toggle + snippets ─── */}
      <div className="raw-text__toolbar">
        <div className="raw-text__type-select">
          <span className="raw-text__label">Default:</span>
          <div className="raw-text__toggle">
            <button
              className={`raw-text__toggle-btn ${defaultType === 'server' ? 'raw-text__toggle-btn--active' : ''}`}
              onClick={() => setDefaultType('server')}
            >
              <Server size={12} />
              Server
            </button>
            <button
              className={`raw-text__toggle-btn ${defaultType === 'client' ? 'raw-text__toggle-btn--active' : ''}`}
              onClick={() => setDefaultType('client')}
            >
              <Monitor size={12} />
              Client
            </button>
          </div>
        </div>

        <div className="raw-text__snippets">
          <button
            className="raw-text__snippet-btn"
            onClick={() => insertTemplate(CSV_TEMPLATE)}
            title="Insert CSV header template"
          >
            <Columns size={12} />
            CSV
          </button>
          <button
            className="raw-text__snippet-btn"
            onClick={() => insertTemplate(TSV_TEMPLATE)}
            title="Insert tab-separated template"
          >
            <LayoutList size={12} />
            TSV
          </button>
        </div>
      </div>

      {/* ─── Editor with line numbers ─── */}
      <div className="raw-text__editor">
        <div className="raw-text__line-numbers" aria-hidden="true">
          {lineNumbers.map((num) => (
            <span key={num} className="raw-text__line-num">{num}</span>
          ))}
        </div>
        <textarea
          ref={textareaRef}
          className="raw-text__input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onScroll={handleScroll}
          placeholder={PLACEHOLDER}
          rows={10}
          spellCheck={false}
          autoComplete="off"
          autoCorrect="off"
        />
      </div>

      {/* ─── Normalize button ─── */}
      <motion.button
        className="btn btn--primary raw-text__normalize-btn"
        onClick={handleNormalize}
        disabled={!text.trim() || loading}
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.98 }}
      >
        <Sparkles size={16} />
        Normalize & Import
      </motion.button>
    </div>
  );
}

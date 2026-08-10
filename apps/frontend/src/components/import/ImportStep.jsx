/* ═══════════════════════════════════════════════════════════
   ImportStep — Redesigned vertical flow layout
   ═══════════════════════════════════════════════════════════ */
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, Type, ChevronDown, ChevronUp } from 'lucide-react';
import FileDropzone from './FileDropzone';
import RawTextInput from './RawTextInput';
import ColumnMapper from './ColumnMapper';
import AssetTable from './AssetTable';
import { useReporterContext } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import './ImportStep.css';

const TABS = [
  { id: 'file', icon: Upload, labelKey: 'import.browse' },
  { id: 'text', icon: Type, labelKey: 'import.paste' },
];

export default function ImportStep({ initialTab = 'file' }) {
  const [activeTab, setActiveTab] = useState(initialTab);
  const [mapperOpen, setMapperOpen] = useState(true);
  const { rows, columnPreview } = useReporterContext();
  const { t } = useI18n();

  // Keep compatibility with callers that switch the import source by event.
  useEffect(() => {
    const handler = (e) => setActiveTab(e.detail || 'text');
    window.addEventListener('reporter:open-tab', handler);
    return () => window.removeEventListener('reporter:open-tab', handler);
  }, []);

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  const showMapper = columnPreview?.columns?.length > 0;
  const showTable = rows?.length > 0;

  return (
    <div className="import-step">
      {/* ─── Source Section ─── */}
      <section className="import-section">
        <div className="import-section__header">
          <h3 className="import-section__title">
            <span className="import-section__num">①</span>
            {t('step.import')}
          </h3>
          <div className="import-tabs">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                className={`import-tab ${activeTab === tab.id ? 'import-tab--active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                <tab.icon size={15} />
                <span>{t(tab.labelKey)}</span>
              </button>
            ))}
          </div>
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
          >
            {activeTab === 'file' && <FileDropzone />}
            {activeTab === 'text' && <RawTextInput />}
          </motion.div>
        </AnimatePresence>
      </section>

      {/* ─── Column Mapper Section ─── */}
      <AnimatePresence>
        {showMapper && (
          <motion.section
            className="import-section"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
          >
            <button
              className="import-section__header import-section__header--toggle"
              onClick={() => setMapperOpen(!mapperOpen)}
            >
              <h3 className="import-section__title">
                <span className="import-section__num">②</span>
                {t('import.columnMap')}
              </h3>
              {mapperOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>
            <AnimatePresence>
              {mapperOpen && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <ColumnMapper />
                </motion.div>
              )}
            </AnimatePresence>
          </motion.section>
        )}
      </AnimatePresence>

      {/* ─── Data Preview Section ─── */}
      <AnimatePresence>
        {showTable && (
          <motion.section
            className="import-section import-section--table"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15, duration: 0.3 }}
          >
            <div className="import-section__header">
              <h3 className="import-section__title">
                <span className="import-section__num">③</span>
                {t('import.preview')}
              </h3>
            </div>
            <AssetTable />
          </motion.section>
        )}
      </AnimatePresence>
    </div>
  );
}

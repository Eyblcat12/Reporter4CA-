/* ═══════════════════════════════════════════════════════════
   PresetManager — Save/load/delete report configuration presets
   ═══════════════════════════════════════════════════════════ */
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Save, Download, Trash2, BookOpen, Plus } from 'lucide-react';
import { useReporterContext } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import './PresetManager.css';

export default function PresetManager() {
  const { presets, fetchPresets, savePreset, loadPreset, deletePreset, loading } =
    useReporterContext();
  const { t } = useI18n();
  const [name, setName] = useState('');
  const [showSave, setShowSave] = useState(false);

  useEffect(() => {
    fetchPresets();
  }, [fetchPresets]);

  const handleSave = async () => {
    if (!name.trim()) return;
    const ok = await savePreset(name.trim());
    if (ok) {
      setName('');
      setShowSave(false);
    }
  };

  const handleLoad = async (presetId) => {
    await loadPreset(presetId);
  };

  const handleDelete = async (presetId) => {
    await deletePreset(presetId);
  };

  return (
    <div className="preset-mgr">
      <div className="preset-mgr__header">
        <h3 className="preset-mgr__title">
          <BookOpen size={16} />
          {t('preset.title')}
        </h3>
        <button className="btn btn--ghost btn--sm" onClick={() => setShowSave(!showSave)}>
          <Plus size={14} />
          {t('preset.save')}
        </button>
      </div>

      {/* Save form */}
      <AnimatePresence>
        {showSave && (
          <motion.div
            className="preset-mgr__save"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
          >
            <input
              className="preset-mgr__input"
              type="text"
              placeholder={t('preset.name') || 'Tên cấu hình...'}
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSave()}
              autoFocus
            />
            <button
              className="btn btn--primary btn--sm"
              onClick={handleSave}
              disabled={!name.trim() || loading}
            >
              <Save size={14} />
              {t('preset.save')}
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Preset list */}
      <div className="preset-mgr__list">
        <AnimatePresence>
          {(presets || []).map((preset) => (
            <motion.div
              key={preset.id}
              className="preset-mgr__item"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, height: 0 }}
            >
              <div className="preset-mgr__item-info">
                <span className="preset-mgr__item-name">{preset.name}</span>
                <span className="preset-mgr__item-date">
                  {preset.updated_at ? new Date(preset.updated_at).toLocaleDateString() : ''}
                </span>
              </div>
              <div className="preset-mgr__item-actions">
                <button
                  className="preset-mgr__action-btn"
                  onClick={() => handleLoad(preset.id)}
                  title={t('preset.load')}
                >
                  <Download size={14} />
                </button>
                <button
                  className="preset-mgr__action-btn preset-mgr__action-btn--delete"
                  onClick={() => handleDelete(preset.id)}
                  title={t('preset.delete')}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {(!presets || presets.length === 0) && (
          <div className="preset-mgr__empty">{t('preset.empty')}</div>
        )}
      </div>
    </div>
  );
}

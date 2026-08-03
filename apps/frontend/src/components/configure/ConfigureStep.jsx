/* ═══════════════════════════════════════════════════════════
   ConfigureStep — Report settings + Presets + Template management
   ═══════════════════════════════════════════════════════════ */
import { useState } from 'react';
import { motion } from 'framer-motion';
import { Settings2, BookOpen, FileStack, Archive, ShieldCheck } from 'lucide-react';
import ReportSettings from './ReportSettings';
import PresetManager from './PresetManager';
import TemplateManager from './TemplateManager';
import WorkspaceBackup from './WorkspaceBackup';
import RuleManager from './RuleManager';
import { useReporterContext } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import './ConfigureStep.css';

export default function ConfigureStep() {
  const { t } = useI18n();
  const [showTemplates, setShowTemplates] = useState(false);

  return (
    <div className="configure-step">
      {/* Report Settings Section */}
      <motion.section
        className="configure-section"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="configure-section__header">
          <div className="configure-section__icon">
            <Settings2 size={18} />
          </div>
          <div className="configure-section__text">
            <h2>{t('configure.title')}</h2>
            <p>{t('configure.subtitle')}</p>
          </div>
        </div>

        <div className="configure-section__body">
          <ReportSettings onManageTemplates={() => setShowTemplates(!showTemplates)} />
        </div>
      </motion.section>

      {/* Template Manager (toggle) */}
      {showTemplates && (
        <motion.section
          className="configure-section"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <div className="configure-section__header">
            <div className="configure-section__icon">
              <FileStack size={18} />
            </div>
            <div className="configure-section__text">
              <h2>{t('template.manage')}</h2>
              <p>{t('template.manageDesc') || 'Upload, phân tích và quản lý template DOCX'}</p>
            </div>
          </div>

          <div className="configure-section__body">
            <TemplateManager onClose={() => setShowTemplates(false)} />
          </div>
        </motion.section>
      )}

      {/* Preset Manager Section */}
      <motion.section className="configure-section" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="configure-section__header">
          <div className="configure-section__icon"><ShieldCheck size={18} /></div>
          <div className="configure-section__text">
            <h2>Detection rules</h2>
            <p>Bật hoặc tắt các quy tắc tạo finding trước khi xuất báo cáo.</p>
          </div>
        </div>
        <div className="configure-section__body"><RuleManager /></div>
      </motion.section>

      {/* Preset Manager Section */}
      <motion.section
        className="configure-section"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="configure-section__header">
          <div className="configure-section__icon">
            <BookOpen size={18} />
          </div>
          <div className="configure-section__text">
            <h2>{t('preset.title')}</h2>
            <p>{t('preset.subtitle') || 'Lưu và tải cấu hình báo cáo'}</p>
          </div>
        </div>

        <div className="configure-section__body">
          <PresetManager />
        </div>
      </motion.section>

      <motion.section
        className="configure-section"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="configure-section__header">
          <div className="configure-section__icon">
            <Archive size={18} />
          </div>
          <div className="configure-section__text">
            <h2>{t('backup.title')}</h2>
            <p>{t('backup.subtitle')}</p>
          </div>
        </div>

        <div className="configure-section__body">
          <WorkspaceBackup />
        </div>
      </motion.section>
    </div>
  );
}

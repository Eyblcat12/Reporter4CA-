/* ═══════════════════════════════════════════════════════════
   TemplateManager — Upload, list, analyze, delete templates
   ═══════════════════════════════════════════════════════════ */
import { useState, useCallback, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload,
  Trash2,
  FileText,
  Wand2,
  X,
  ChevronUp,
  Info,
  Star,
  Sparkles,
  Clock,
} from 'lucide-react';
import { useReporterContext } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import './TemplateManager.css';
import TemplateThumbnail from './TemplateThumbnail';
import TemplateVersions from './TemplateVersions';

const REPORT_TYPES = [
  { id: 'full', label: 'Đầy đủ' },
  { id: 'server_only', label: 'Chỉ Server' },
  { id: 'client_only', label: 'Chỉ Client' },
  { id: 'summary', label: 'Tóm tắt' },
  { id: 'technical', label: 'Kỹ thuật' },
  { id: 'incident_response', label: 'Incident Response' },
];

export default function TemplateManager({ onClose }) {
  const {
    templates,
    uploadTemplate,
    updateTemplate,
    deleteTemplate,
    analyzeTemplate,
    setReportSettings,
    reportSettings,
    fetchReportHistory,
    reportHistory,
  } = useReporterContext();
  const { t } = useI18n();
  const fileInputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const [analysisData, setAnalysisData] = useState(null);
  const [analysisId, setAnalysisId] = useState(null);
  const [uploadName, setUploadName] = useState('');
  const [activeType, setActiveType] = useState(reportSettings.reportType || 'full');
  const [makeDefault, setMakeDefault] = useState(false);
  const [versionsId, setVersionsId] = useState(null);
  const visibleTemplates = (templates || []).filter(
    (tpl) => (tpl.reportType || 'full') === activeType,
  );

  const handleFiles = useCallback(
    async (files) => {
      const file = files[0];
      if (!file) return;
      if (!file.name.toLowerCase().endsWith('.docx')) {
        alert('Chỉ chấp nhận file .docx');
        return;
      }
      const reader = new FileReader();
      reader.onload = async () => {
        const uploaded = await uploadTemplate(
          file.name,
          reader.result,
          uploadName || '',
          '',
          activeType,
          makeDefault,
        );
        if (uploaded?.analysis) {
          setAnalysisData(uploaded.analysis);
          setAnalysisId(uploaded.id);
        }
        setUploadName('');
        setMakeDefault(false);
      };
      reader.readAsDataURL(file);
    },
    [uploadTemplate, uploadName, activeType, makeDefault],
  );

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      setDragOver(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles],
  );

  const handleAnalyze = async (tpl) => {
    if (analysisId === tpl.id) {
      setAnalysisId(null);
      setAnalysisData(null);
      return;
    }
    const result = await analyzeTemplate(tpl.id);
    setAnalysisData(result?.analysis || null);
    setAnalysisId(tpl.id);
  };

  const handleSelect = (tpl) => {
    if (tpl.compatibilityStatus === 'incompatible') return;
    setReportSettings({
      ...reportSettings,
      reportType: tpl.reportType || activeType,
      templatePath: tpl.path,
    });
    if (onClose) onClose();
  };

  // Fetch history on mount
  useEffect(() => {
    fetchReportHistory?.();
  }, [fetchReportHistory]);

  // Deduplicate recently used templates from report history
  const recentTemplates = (() => {
    if (!reportHistory?.length) return [];
    const seen = new Set();
    const results = [];
    for (const report of reportHistory) {
      const historyType = report.reportType || report.report_type || 'full';
      if (historyType !== activeType) continue;
      const tplName = report.templateName || report.template_name;
      const tplPath = report.templatePath || report.template_path;
      if (tplPath && !seen.has(tplPath)) {
        seen.add(tplPath);
        results.push({
          name: tplName || tplPath.split('/').pop()?.split('\\').pop() || 'Unknown',
          path: tplPath,
          date: report.createdAt || report.created_at || '',
          servers: report.counts?.servers || report.server_count || 0,
          clients: report.counts?.clients || report.client_count || 0,
        });
      }
      if (results.length >= 5) break;
    }
    return results;
  })();

  return (
    <div className="tpl-mgr">
      <div className="tpl-mgr__header">
        <h3 className="tpl-mgr__title">
          <FileText size={18} />
          {t('template.manage')}
        </h3>
        {onClose && (
          <button className="tpl-mgr__close" onClick={onClose}>
            <X size={18} />
          </button>
        )}
      </div>

      <div className="tpl-mgr__type-tabs" role="tablist" aria-label="Loại báo cáo">
        {REPORT_TYPES.map((type) => {
          const count = (templates || []).filter(
            (tpl) => (tpl.reportType || 'full') === type.id,
          ).length;
          return (
            <button
              key={type.id}
              type="button"
              role="tab"
              aria-selected={activeType === type.id}
              className={`tpl-mgr__type-tab ${activeType === type.id ? 'tpl-mgr__type-tab--active' : ''}`}
              onClick={() => setActiveType(type.id)}
            >
              <span>{type.label}</span>
              <small>{count}</small>
            </button>
          );
        })}
      </div>

      {/* Upload Zone */}
      <div
        className={`tpl-mgr__dropzone ${dragOver ? 'tpl-mgr__dropzone--active' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <Upload size={28} className="tpl-mgr__dropzone-icon" />
        <span className="tpl-mgr__dropzone-text">{t('template.dropzone')}</span>
        <span className="tpl-mgr__dropzone-hint">.docx — Max 20MB</span>
        <input
          ref={fileInputRef}
          type="file"
          accept=".docx"
          style={{ display: 'none' }}
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {/* Template name input */}
      <div className="tpl-mgr__upload-name">
        <input
          type="text"
          placeholder={t('template.namePlaceholder') || 'Tên template (tuỳ chọn)...'}
          value={uploadName}
          onChange={(e) => setUploadName(e.target.value)}
          className="tpl-mgr__name-input"
        />
        <label className="tpl-mgr__default-check">
          <input
            type="checkbox"
            checked={makeDefault}
            onChange={(e) => setMakeDefault(e.target.checked)}
          />
          Đặt làm mặc định cho {REPORT_TYPES.find((type) => type.id === activeType)?.label}
        </label>
      </div>

      {/* Recently Used Templates */}
      {recentTemplates.length > 0 && (
        <div className="tpl-mgr__recent">
          <h4 className="tpl-mgr__section-title">
            <Clock size={14} />
            Đã dùng gần đây
          </h4>
          <div className="tpl-mgr__recent-list">
            {recentTemplates.map((rt, idx) => (
              <motion.div
                key={rt.path + idx}
                className={`tpl-mgr__recent-item ${reportSettings.templatePath === rt.path ? 'tpl-mgr__recent-item--active' : ''}`}
                onClick={() => setReportSettings({ ...reportSettings, templatePath: rt.path })}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.05 }}
                whileHover={{ scale: 1.01 }}
              >
                <FileText size={14} className="tpl-mgr__recent-icon" />
                <div className="tpl-mgr__recent-info">
                  <span className="tpl-mgr__recent-name">{rt.name}</span>
                  {rt.date && (
                    <span className="tpl-mgr__recent-date">
                      {new Date(rt.date).toLocaleDateString('vi-VN')}
                      {' · '}
                      {rt.servers}S / {rt.clients}C
                    </span>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Template List */}
      <div className="tpl-mgr__list">
        <AnimatePresence>
          {visibleTemplates.map((tpl) => (
            <motion.div
              key={tpl.id || tpl.filename}
              className={`tpl-mgr__item ${reportSettings.templatePath === tpl.path ? 'tpl-mgr__item--selected' : ''}`}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, height: 0 }}
            >
              <div
                className="tpl-mgr__item-main"
                onClick={() => handleSelect(tpl)}
                aria-disabled={tpl.compatibilityStatus === 'incompatible'}
              >
                <TemplateThumbnail template={tpl} />
                <div className="tpl-mgr__item-info">
                  <span className="tpl-mgr__item-name">{tpl.name}</span>
                  <span className="tpl-mgr__item-meta">
                    {(tpl.size / 1024).toFixed(0)} KB
                    {tpl.filename && <> · {tpl.filename}</>}
                  </span>
                  <span className="tpl-mgr__item-category">
                    {REPORT_TYPES.find((type) => type.id === (tpl.reportType || 'full'))?.label}
                  </span>
                </div>
                <div className="tpl-mgr__item-badges">
                  {tpl.isDefault && (
                    <span className="tpl-badge tpl-badge--default">
                      <Star size={10} /> {t('template.default')}
                    </span>
                  )}
                  {tpl.isGenerated && (
                    <span className="tpl-badge tpl-badge--generated">
                      <Sparkles size={10} /> {t('template.fromReport') || 'Từ báo cáo'}
                    </span>
                  )}
                  {tpl.hasTokens && (
                    <span className="tpl-badge tpl-badge--tokens">
                      <Wand2 size={10} /> Tokens
                    </span>
                  )}
                  {tpl.compatibilityStatus && tpl.compatibilityStatus !== 'unknown' && (
                    <span className={`tpl-badge tpl-badge--${tpl.compatibilityStatus}`}>
                      {t(`template.compatibility.${tpl.compatibilityStatus}`)}
                    </span>
                  )}
                </div>
              </div>

              <div className="tpl-mgr__item-actions">
                <select
                  className="tpl-mgr__category-select"
                  value={tpl.reportType || 'full'}
                  onClick={(e) => e.stopPropagation()}
                  onChange={(e) => updateTemplate(tpl.id, { reportType: e.target.value })}
                  aria-label={`Phân loại template ${tpl.name}`}
                >
                  {REPORT_TYPES.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.label}
                    </option>
                  ))}
                </select>
                {!tpl.isDefault && tpl.compatibilityStatus !== 'incompatible' && (
                  <button
                    className="tpl-mgr__action-btn"
                    onClick={() => updateTemplate(tpl.id, { isDefault: true })}
                    title="Đặt làm template mặc định cho loại báo cáo này"
                  >
                    <Star size={14} />
                  </button>
                )}
                <button
                  className="tpl-mgr__action-btn"
                  onClick={() => handleAnalyze(tpl)}
                  title="Phân tích"
                >
                  {analysisId === tpl.id ? <ChevronUp size={14} /> : <Info size={14} />}
                </button>
                <button
                  className="tpl-mgr__action-btn"
                  onClick={() => setVersionsId(versionsId === tpl.id ? null : tpl.id)}
                  title="Lịch sử phiên bản"
                >
                  <Clock size={14} />
                </button>
                {!tpl.isDefault && (
                  <button
                    className="tpl-mgr__action-btn tpl-mgr__action-btn--delete"
                    onClick={() => deleteTemplate(tpl.id)}
                    title={t('template.delete')}
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>

              {/* Analysis Panel */}
              <AnimatePresence>
                {analysisId === tpl.id && analysisData && (
                  <motion.div
                    className="tpl-mgr__analysis"
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <div className="tpl-analysis__grid">
                      <div className="tpl-analysis__item">
                        <span className="tpl-analysis__label">Mode</span>
                        <span className="tpl-analysis__value">{analysisData.templateMode}</span>
                      </div>
                      <div className="tpl-analysis__item">
                        <span className="tpl-analysis__label">Tables</span>
                        <span className="tpl-analysis__value">{analysisData.tableCount}</span>
                      </div>
                      <div className="tpl-analysis__item">
                        <span className="tpl-analysis__label">Headings</span>
                        <span className="tpl-analysis__value">{analysisData.headingCount}</span>
                      </div>
                      <div className="tpl-analysis__item">
                        <span className="tpl-analysis__label">Pages (est.)</span>
                        <span className="tpl-analysis__value">~{analysisData.pageEstimate}</span>
                      </div>
                    </div>
                    {analysisData.tokensFound?.length > 0 && (
                      <div className="tpl-analysis__tokens">
                        <span className="tpl-analysis__label">Tokens:</span>
                        {analysisData.tokensFound.map((tok) => (
                          <code key={tok} className="tpl-analysis__token">
                            {tok}
                          </code>
                        ))}
                      </div>
                    )}
                    {analysisData.headingList?.length > 0 && (
                      <div className="tpl-analysis__headings">
                        <span className="tpl-analysis__label">Headings:</span>
                        <ul>
                          {analysisData.headingList.slice(0, 8).map((h, i) => (
                            <li key={i}>{h}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {analysisData.prototypeTables?.length > 0 && (
                      <div className="tpl-analysis__protos">
                        <span className="tpl-analysis__label">Bảng mẫu:</span>
                        {analysisData.prototypeTables.map((p) => (
                          <span key={p} className="tpl-badge tpl-badge--proto">
                            {p}
                          </span>
                        ))}
                      </div>
                    )}
                    {analysisData.compatibility && (
                      <div
                        className={`tpl-analysis__compat tpl-analysis__compat--${analysisData.compatibility.status}`}
                      >
                        <strong>
                          {t(`template.compatibility.${analysisData.compatibility.status}`)}
                        </strong>
                        <span>
                          Schema {analysisData.compatibility.version} ·{' '}
                          {analysisData.compatibility.reportType}
                        </span>
                        {[
                          ...(analysisData.compatibility.errors || []),
                          ...(analysisData.compatibility.warnings || []),
                        ].map((issue) => (
                          <p key={`${issue.code}-${issue.item}`}>
                            <code>{issue.item}</code> — {issue.message}
                          </p>
                        ))}
                        {analysisData.compatibility.guidance?.map((item) => (
                          <small key={item}>• {item}</small>
                        ))}
                      </div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
              {versionsId === tpl.id && <TemplateVersions template={tpl} />}
            </motion.div>
          ))}
        </AnimatePresence>

        {visibleTemplates.length === 0 && (
          <div className="tpl-mgr__empty">
            <FileText size={24} />
            <span>Chưa có template cho loại báo cáo này</span>
          </div>
        )}
      </div>
    </div>
  );
}

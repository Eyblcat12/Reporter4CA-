/* ═══════════════════════════════════════════════════════════
   ReportSettings — Premium form with icon + label rows
   ═══════════════════════════════════════════════════════════ */
import { useEffect, useMemo } from 'react';
import {
  FileText,
  Building2,
  Calendar,
  FileStack,
  FolderOpen,
  FileOutput,
  ChevronDown,
  ToggleLeft,
  ToggleRight,
} from 'lucide-react';
import { useReporterContext, validateIncidentMetadata } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import './ReportSettings.css';

export default function ReportSettings({ onManageTemplates }) {
  const { reportSettings, setReportSettings, templates, fetchTemplates } =
    useReporterContext();
  const { t } = useI18n();
  const compatibleTemplates = (templates || []).filter(
    (tpl) => (tpl.reportType || 'full') === (reportSettings.reportType || 'full')
      && tpl.compatibilityStatus !== 'incompatible',
  );
  const incidentQuality = useMemo(
    () => validateIncidentMetadata(reportSettings.incidentMetadata || {}),
    [reportSettings.incidentMetadata],
  );

  useEffect(() => {
    fetchTemplates();
  }, []);

  const update = (field, value) => {
    setReportSettings({ ...reportSettings, [field]: value });
  };

  const updateIncident = (field, value) => {
    update('incidentMetadata', {
      ...(reportSettings.incidentMetadata || {}),
      [field]: value,
    });
  };

  return (
    <div className="rs">
      {/* Title */}
      <div className="rs__field">
        <label className="rs__label">
          <FileText size={16} className="rs__label-icon" />
          <span>{t('configure.reportTitle')}</span>
        </label>
        <div className="rs__input-wrap">
          <input
            type="text"
            className="rs__input"
            value={reportSettings.title || ''}
            onChange={(e) => update('title', e.target.value)}
            placeholder="BÁO CÁO ĐÁNH GIÁ AN TOÀN THÔNG TIN"
          />
        </div>
      </div>

      <div className="rs__divider" />

      {reportSettings.reportType === 'incident_response' && (
        <div className="rs__incident">
          <h3 className="rs__incident-title">Thông tin Incident Response</h3>
          <section className={`rs__readiness ${incidentQuality.valid ? 'rs__readiness--ready' : 'rs__readiness--blocked'}`} aria-label="Mức sẵn sàng Incident Response">
            <div className="rs__readiness-head">
              <div>
                <strong>{incidentQuality.valid ? 'Sẵn sàng tạo báo cáo' : 'Chưa sẵn sàng'}</strong>
                <span>{incidentQuality.errors.length} lỗi · {incidentQuality.warnings.length} cảnh báo</span>
              </div>
              <span className="rs__readiness-badge">{incidentQuality.valid ? 'READY' : 'BLOCKED'}</span>
            </div>
            <div className="rs__readiness-stats">
              <span><strong>{incidentQuality.summary.timelineEvents}</strong> Timeline</span>
              <span><strong>{incidentQuality.summary.iocs}</strong> IoC</span>
              <span><strong>{incidentQuality.summary.actions}</strong> Actions</span>
              <span><strong>{incidentQuality.summary.evidenceReferences}</strong> Evidence</span>
            </div>
            {(incidentQuality.errors.length > 0 || incidentQuality.warnings.length > 0) && (
              <ul className="rs__readiness-issues">
                {incidentQuality.errors.slice(0, 3).map((item, index) => (
                  <li className="rs__readiness-error" key={`error-${item.code}-${index}`}>{item.message}</li>
                ))}
                {incidentQuality.warnings.slice(0, 2).map((item, index) => (
                  <li className="rs__readiness-warning" key={`warning-${item.code}-${index}`}>{item.message}</li>
                ))}
              </ul>
            )}
          </section>
          <div className="rs__incident-grid">
            <label className="rs__incident-field">
              <span>Mã sự cố</span>
              <input className="rs__input" value={reportSettings.incidentMetadata?.incidentId || ''} onChange={(e) => updateIncident('incidentId', e.target.value)} placeholder="IR-2026-001" />
            </label>
            <label className="rs__incident-field">
              <span>Mức độ</span>
              <select className="rs__input rs__select" value={reportSettings.incidentMetadata?.severity || 'High'} onChange={(e) => updateIncident('severity', e.target.value)}>
                <option>Critical</option><option>High</option><option>Medium</option><option>Low</option>
              </select>
            </label>
            <label className="rs__incident-field">
              <span>Trạng thái</span>
              <input className="rs__input" value={reportSettings.incidentMetadata?.status || ''} onChange={(e) => updateIncident('status', e.target.value)} />
            </label>
            <label className="rs__incident-field">
              <span>Thời điểm phát hiện</span>
              <input type="datetime-local" className="rs__input" value={reportSettings.incidentMetadata?.detectedAt || ''} onChange={(e) => updateIncident('detectedAt', e.target.value)} />
            </label>
          </div>
          {[
            ['executiveSummary', 'Tóm tắt điều hành'],
            ['containmentActions', 'Hành động khoanh vùng'],
            ['eradicationActions', 'Hành động loại bỏ'],
            ['recoveryActions', 'Hành động khôi phục'],
            ['lessonsLearned', 'Bài học kinh nghiệm'],
          ].map(([field, label]) => (
            <label key={field} className="rs__incident-field rs__incident-field--wide">
              <span>{label}</span>
              <textarea
                className="rs__input rs__textarea" rows="3"
                value={reportSettings.incidentMetadata?.[field] || ''}
                onChange={(e) => updateIncident(field, e.target.value)}
                placeholder={field.endsWith('Actions') ? 'Hành động | Trạng thái | Người phụ trách | Evidence ID' : ''}
              />
            </label>
          ))}
          <label className="rs__incident-field rs__incident-field--wide">
            <span>Timeline (mỗi dòng: thời gian | sự kiện)</span>
            <textarea
              className="rs__input rs__textarea"
              rows="4"
              value={reportSettings.incidentMetadata?.timelineText || ''}
              onChange={(e) => updateIncident('timelineText', e.target.value)}
              placeholder={'Thời gian | Sự kiện | Evidence ID | IoC liên quan\n2026-07-17 09:30 | Phát hiện cảnh báo EDR | EDR-001 | 203.0.113.10'}
            />
          </label>
          <label className="rs__incident-field rs__incident-field--wide">
            <span>Indicators of Compromise (mỗi dòng: loại | giá trị)</span>
            <textarea
              className="rs__input rs__textarea"
              rows="4"
              value={reportSettings.incidentMetadata?.iocsText || ''}
              onChange={(e) => updateIncident('iocsText', e.target.value)}
              placeholder={'Loại | Giá trị | Nguồn evidence\nIP | 203.0.113.10 | EDR-001'}
            />
          </label>
        </div>
      )}

      {reportSettings.reportType === 'incident_response' && <div className="rs__divider" />}

      {/* Organization */}
      <div className="rs__field">
        <label className="rs__label">
          <Building2 size={16} className="rs__label-icon" />
          <span>{t('configure.org')}</span>
        </label>
        <div className="rs__input-wrap">
          <input
            type="text"
            className="rs__input"
            value={reportSettings.organization || ''}
            onChange={(e) => update('organization', e.target.value)}
            placeholder="Tên đơn vị / tổ chức..."
          />
        </div>
      </div>

      <div className="rs__divider" />

      {/* Assessment Date */}
      <div className="rs__field">
        <label className="rs__label">
          <Calendar size={16} className="rs__label-icon" />
          <span>{t('configure.date')}</span>
        </label>
        <div className="rs__input-wrap">
          <input
            type="date"
            className="rs__input rs__input--date"
            value={reportSettings.assessmentDate || ''}
            onChange={(e) => update('assessmentDate', e.target.value)}
          />
        </div>
      </div>

      <div className="rs__divider" />

      {/* Template */}
      <div className="rs__field">
        <label className="rs__label">
          <FileStack size={16} className="rs__label-icon" />
          <span>{t('configure.template')}</span>
        </label>
        <div className="rs__input-wrap rs__select-wrap">
          <select
            className="rs__input rs__select"
            value={reportSettings.templatePath || ''}
            onChange={(e) => update('templatePath', e.target.value)}
          >
            <option value="">— Template mặc định —</option>
            {compatibleTemplates.map((tpl) => (
              <option key={tpl.id || tpl.filename} value={tpl.path}>
                {tpl.name}{tpl.size ? ` (${(tpl.size / 1024).toFixed(0)} KB)` : ''}
                {tpl.isDefault ? ' ★' : ''}
                {tpl.isGenerated ? ' ◆' : ''}
              </option>
            ))}
          </select>
          <ChevronDown size={14} className="rs__select-chevron" />
        </div>
        {onManageTemplates && (
          <button
            type="button"
            className="rs__manage-btn"
            onClick={onManageTemplates}
          >
            <FileStack size={12} />
            {t('template.manage')}
          </button>
        )}
      </div>

      <div className="rs__divider" />

      {/* Disable Plugins Toggle */}
      <div className="rs__field">
        <label className="rs__label">
          {reportSettings.disablePlugins ? (
            <ToggleLeft size={16} className="rs__label-icon" />
          ) : (
            <ToggleRight size={16} className="rs__label-icon rs__label-icon--active" />
          )}
          <span>{t('configure.plugins')}</span>
        </label>
        <div className="rs__input-wrap rs__toggle-wrap">
          <button
            type="button"
            className={`rs__toggle ${!reportSettings.disablePlugins ? 'rs__toggle--active' : ''}`}
            onClick={() => update('disablePlugins', !reportSettings.disablePlugins)}
            aria-label="Toggle plugins"
          >
            <span className="rs__toggle-thumb" />
          </button>
          <span className="rs__toggle-label">
            {reportSettings.disablePlugins ? 'Disabled' : 'Enabled'}
          </span>
        </div>
      </div>

      <div className="rs__divider" />

      {/* Plugins Directory */}
      <div className="rs__field">
        <label className="rs__label">
          <FolderOpen size={16} className="rs__label-icon" />
          <span>{t('configure.pluginsDir')}</span>
        </label>
        <div className="rs__input-wrap">
          <input
            type="text"
            className="rs__input"
            value={reportSettings.pluginsDir || ''}
            onChange={(e) => update('pluginsDir', e.target.value)}
            placeholder="./plugins"
          />
        </div>
      </div>

      <div className="rs__divider" />

      {/* Output File Name */}
      <div className="rs__field">
        <label className="rs__label">
          <FileOutput size={16} className="rs__label-icon" />
          <span>{t('configure.outputName')}</span>
        </label>
        <div className="rs__input-wrap">
          <input
            type="text"
            className="rs__input"
            value={reportSettings.outputName || ''}
            onChange={(e) => update('outputName', e.target.value)}
            placeholder="reporter-output"
          />
        </div>
      </div>
    </div>
  );
}

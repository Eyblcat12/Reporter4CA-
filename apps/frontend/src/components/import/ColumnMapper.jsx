/* ═══════════════════════════════════════════════════════════
   ColumnMapper — Premium column mapping interface
   ═══════════════════════════════════════════════════════════ */
import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Wand2, Check, AlertCircle, ChevronDown } from 'lucide-react';
import { useReporterContext } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import './ColumnMapper.css';

const TARGET_FIELDS = [
  { value: '', label: '— Bỏ qua —', labelEn: '— Skip —' },
  { value: 'hostname', label: 'Hostname (chung)', labelEn: 'Hostname (general)', required: true },
  { value: 'hostname_server', label: 'Hostname (Máy chủ)', labelEn: 'Hostname (Server)' },
  { value: 'hostname_client', label: 'Hostname (Máy trạm)', labelEn: 'Hostname (Client)' },
  { value: 'ip', label: 'Địa chỉ IP', labelEn: 'IP Address' },
  { value: 'os', label: 'Hệ điều hành / OS', labelEn: 'Operating System' },
  { value: 'type', label: 'Loại (Server/Client)', labelEn: 'Type (Server/Client)' },
  { value: 'result', label: 'Kết quả đánh giá', labelEn: 'Assessment Result' },
  { value: 'notes', label: 'Ghi chú / Notes', labelEn: 'Notes' },
  { value: 'status', label: 'Trạng thái', labelEn: 'Status' },
];

export default function ColumnMapper() {
  const {
    columnPreview,
    columnMapping,
    setColumnMapping,
    applyColumnMapping,
    loading,
  } = useReporterContext();
  const { t } = useI18n();

  const columns = columnPreview?.columns || [];
  const sampleRows = columnPreview?.sampleRows || [];
  const suggested = columnPreview?.suggestedMapping || {};

  const currentMapping = columnMapping || {};

  const handleAutoDetect = () => {
    setColumnMapping({ ...suggested });
  };

  const handleChange = (sourceCol, targetField) => {
    setColumnMapping({
      ...currentMapping,
      [sourceCol]: targetField,
    });
  };

  const handleApply = () => {
    applyColumnMapping();
  };

  const usedTargets = useMemo(() => {
    const used = new Set();
    Object.values(currentMapping).forEach(v => { if (v) used.add(v); });
    return used;
  }, [currentMapping]);

  const hasHostname = usedTargets.has('hostname') || usedTargets.has('hostname_server') || usedTargets.has('hostname_client');

  const getSampleValues = (col) => {
    if (!sampleRows.length) return [];
    return sampleRows
      .slice(0, 3)
      .map(row => {
        const val = row?.[col];
        return val ? String(val).substring(0, 24) : '';
      })
      .filter(Boolean);
  };

  // Kiểm tra xung đột hostname vs hostname_server/hostname_client
  const isHostnameDisabled = (fieldValue, colCurrentMapping) => {
    if (!fieldValue) return false;
    // Đã được dùng bởi cột khác
    if (usedTargets.has(fieldValue) && colCurrentMapping !== fieldValue) return true;
    // hostname <-> hostname_server/hostname_client là xung đột
    if (fieldValue === 'hostname' && (usedTargets.has('hostname_server') || usedTargets.has('hostname_client'))) return true;
    if ((fieldValue === 'hostname_server' || fieldValue === 'hostname_client') && usedTargets.has('hostname')) return true;
    return false;
  };

  if (!columns.length) return null;

  return (
    <div className="column-mapper">
      <div className="column-mapper__header">
        <h3 className="column-mapper__title">{t('import.columnMap')}</h3>
        <div className="column-mapper__actions">
          <button className="btn btn--ghost btn--sm" onClick={handleAutoDetect}>
            <Wand2 size={14} />
            {t('import.columnMap.auto')}
          </button>
          <button
            className="btn btn--primary btn--sm"
            onClick={handleApply}
            disabled={!hasHostname || loading}
          >
            <Check size={14} />
            Áp dụng
          </button>
        </div>
      </div>

      {!hasHostname && Object.keys(currentMapping).length > 0 && (
        <div className="column-mapper__warning">
          <AlertCircle size={14} />
          <span>Cần ánh xạ ít nhất một cột Hostname: chung, máy chủ, hoặc máy trạm</span>
        </div>
      )}

      <div className="column-mapper__list">
        {columns.map((col, idx) => {
          const mapped = currentMapping[col] || '';
          const isMapped = !!mapped;
          const samples = getSampleValues(col);

          return (
            <motion.div
              key={col}
              className={`column-mapper__row ${isMapped ? 'column-mapper__row--mapped' : ''}`}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.04, duration: 0.2 }}
            >
              <div className="column-mapper__source">
                <span className="column-mapper__col-name">{col}</span>
                <div className="column-mapper__samples">
                  {samples.map((s, i) => (
                    <span key={i} className="column-mapper__sample">{s}</span>
                  ))}
                </div>
              </div>

              <span className="column-mapper__arrow">→</span>

              <div className="column-mapper__target">
                <div className="select-wrapper">
                  <select
                    value={mapped}
                    onChange={(e) => handleChange(col, e.target.value)}
                  >
                    {TARGET_FIELDS.map(f => (
                      <option
                        key={f.value}
                        value={f.value}
                        disabled={isHostnameDisabled(f.value, currentMapping[col])}
                      >
                        {f.label} {f.required ? '★' : ''}
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={14} className="select-icon" />
                </div>
              </div>

              <div className="column-mapper__status">
                {isMapped ? (
                  <Check size={16} className="text-success" />
                ) : (
                  <span className="column-mapper__dot" />
                )}
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

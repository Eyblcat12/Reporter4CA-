/* ═══════════════════════════════════════════════════════════
   FileDropzone — Premium file upload with drag-over effects
   ═══════════════════════════════════════════════════════════ */
import { useCallback, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  UploadCloud,
  FileSpreadsheet,
  FileCode,
  FileText,
  X,
  FlaskConical,
} from 'lucide-react';
import { useReporterContext } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import './FileDropzone.css';

const ACCEPTED = '.xlsx,.xls,.csv,.json,.txt,.tsv';

function getFileIcon(filename) {
  if (!filename) return FileText;
  const ext = filename.split('.').pop()?.toLowerCase();
  if (['xlsx', 'xls'].includes(ext)) return FileSpreadsheet;
  if (['json'].includes(ext)) return FileCode;
  return FileText;
}

function getFileExt(filename) {
  if (!filename) return '';
  return filename.split('.').pop()?.toUpperCase() || '';
}

function formatSize(bytes) {
  if (!bytes || bytes === 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FileDropzone() {
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef(null);
  const { importedFile, importFile, loadSample, loading, clearImportedFile } = useReporterContext();
  const { t } = useI18n();

  const handleFile = useCallback(
    (file) => {
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = reader.result;
        importFile(file.name, base64, file.size);
      };
      reader.readAsDataURL(file);
    },
    [importFile]
  );

  const onDrop = useCallback(
    (e) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer?.files?.[0];
      handleFile(file);
    },
    [handleFile]
  );

  const onDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };
  const onDragLeave = () => setDragOver(false);
  const onBrowse = () => fileRef.current?.click();
  const onFileChange = (e) => handleFile(e.target.files?.[0]);

  const clearFile = (e) => {
    e?.stopPropagation();
    if (fileRef.current) fileRef.current.value = '';
    clearImportedFile();
  };

  const FileIcon = importedFile ? getFileIcon(importedFile.name) : UploadCloud;

  return (
    <div className="dropzone-wrapper">
      <input
        ref={fileRef}
        type="file"
        accept={ACCEPTED}
        onChange={onFileChange}
        className="dropzone__input"
      />

      <AnimatePresence mode="wait">
        {importedFile ? (
          /* ─── Uploaded state ─── */
          <motion.div
            key="uploaded"
            className="dropzone dropzone--has-file"
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.96 }}
            transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
          >
            <div className="dropzone__file-card">
              <div className="dropzone__file-icon-wrap">
                <FileIcon size={28} strokeWidth={1.5} />
              </div>
              <div className="dropzone__file-meta">
                <span className="dropzone__filename">{importedFile.name}</span>
                <span className="dropzone__filesize">
                  {formatSize(importedFile.size)}
                </span>
              </div>
              <span className="dropzone__format-badge">{getFileExt(importedFile.name)}</span>
              <button
                type="button"
                className="dropzone__remove"
                onClick={clearFile}
                title={t('common.delete')}
                aria-label={`Xóa file ${importedFile.name}`}
              >
                <X size={16} />
              </button>
            </div>

            {/* Loading overlay */}
            <AnimatePresence>
              {loading && (
                <motion.div
                  className="dropzone__loading-overlay"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <div className="dropzone__progress-bar">
                    <div className="dropzone__progress-fill" />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        ) : (
          /* ─── Empty / Drag state ─── */
          <motion.div
            key="empty"
            className={`dropzone ${dragOver ? 'dropzone--over' : ''}`}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.96 }}
            transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
            onClick={onBrowse}
          >
            <motion.div
              className="dropzone__icon-ring"
              animate={
                dragOver
                  ? { scale: 1.12, rotate: 4 }
                  : { scale: 1, rotate: 0 }
              }
              transition={{ type: 'spring', stiffness: 300, damping: 20 }}
            >
              <UploadCloud size={36} strokeWidth={1.5} />
            </motion.div>
            <div className="dropzone__text-group">
              <p className="dropzone__text">{t('import.dropzone')}</p>
              <p className="dropzone__hint">.xlsx · .xls · .csv · .json · .txt · .tsv</p>
            </div>

            {/* Loading overlay */}
            <AnimatePresence>
              {loading && (
                <motion.div
                  className="dropzone__loading-overlay"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <div className="dropzone__progress-bar">
                    <div className="dropzone__progress-fill" />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── Action buttons ─── */}
      <div className="dropzone__actions">
        <button className="btn btn--primary" onClick={onBrowse} disabled={loading}>
          <UploadCloud size={16} />
          {t('import.browse')}
        </button>
        <button className="btn btn--ghost" onClick={loadSample} disabled={loading}>
          <FlaskConical size={16} />
          {t('import.sample')}
        </button>
      </div>
    </div>
  );
}

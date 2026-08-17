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
  Check,
  LoaderCircle,
  AlertCircle,
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
  const readerRef = useRef(null);
  const {
    importedFile,
    importFile,
    importProgress,
    setImportProgress,
    loadSample,
    loading,
    clearImportedFile,
  } = useReporterContext();
  const { t } = useI18n();
  const progress = Math.min(100, Math.max(0, importProgress?.progress || 0));
  const importBusy = importProgress?.status === 'running';
  const progressMessages = {
    reading: t('import.progress.reading'),
    analyzing: t('import.progress.analyzing'),
    mapping: `${t('import.progress.detected')} ${importProgress?.columnCount || 0}`,
    importing: t('import.progress.importing'),
    validating: t('import.progress.validating'),
    'mapping-required': t('import.progress.mappingRequired'),
    completed:
      importProgress?.rowCount > 0
        ? `${t('import.progress.completed')} · ${importProgress.rowCount} ${t('import.progress.rowsReady')}`
        : t('import.progress.completedEmpty'),
  };
  const progressMessage =
    importProgress?.status === 'failed'
      ? importProgress.message || t('import.progress.failed')
      : progressMessages[importProgress?.phase] ||
        importProgress?.message ||
        t('import.progress.preparing');

  const handleFile = useCallback(
    (file) => {
      if (!file) return;
      const reader = new FileReader();
      readerRef.current = reader;
      setImportProgress({
        status: 'running',
        phase: 'reading',
        progress: 0,
        message: t('import.progress.reading'),
        filename: file.name,
        rowCount: 0,
      });
      reader.onprogress = (event) => {
        if (!event.lengthComputable) return;
        setImportProgress({
          progress: Math.min(20, Math.round((event.loaded / event.total) * 20)),
        });
      };
      reader.onload = () => {
        readerRef.current = null;
        setImportProgress({ progress: 20, message: t('import.progress.uploading') });
        const base64 = reader.result;
        importFile(file.name, base64, file.size);
      };
      reader.onerror = () => {
        readerRef.current = null;
        setImportProgress({
          status: 'failed',
          phase: 'failed',
          message: t('import.progress.readError'),
        });
      };
      reader.onabort = () => {
        readerRef.current = null;
      };
      reader.readAsDataURL(file);
    },
    [importFile, setImportProgress, t],
  );

  const onDrop = useCallback(
    (e) => {
      e.preventDefault();
      setDragOver(false);
      if (importBusy) return;
      const file = e.dataTransfer?.files?.[0];
      handleFile(file);
    },
    [handleFile, importBusy],
  );

  const onDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };
  const onDragLeave = () => setDragOver(false);
  const onBrowse = () => {
    if (!importBusy) fileRef.current?.click();
  };
  const onFileChange = (e) => handleFile(e.target.files?.[0]);

  const clearFile = (e) => {
    e?.stopPropagation();
    readerRef.current?.abort();
    readerRef.current = null;
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
            className={`dropzone dropzone--has-file ${importBusy ? 'dropzone--busy' : ''}`}
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
                <span className="dropzone__filesize">{formatSize(importedFile.size)}</span>
              </div>
              <span className="dropzone__format-badge">{getFileExt(importedFile.name)}</span>
              {!importBusy && (
                <button
                  type="button"
                  className="dropzone__remove"
                  onClick={clearFile}
                  title={t('common.delete')}
                  aria-label={`${t('common.delete')} ${importedFile.name}`}
                >
                  <X size={16} />
                </button>
              )}
            </div>
          </motion.div>
        ) : (
          /* ─── Empty / Drag state ─── */
          <motion.div
            key="empty"
            className={`dropzone ${dragOver ? 'dropzone--over' : ''} ${importBusy ? 'dropzone--busy' : ''}`}
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
              animate={dragOver ? { scale: 1.12, rotate: 4 } : { scale: 1, rotate: 0 }}
              transition={{ type: 'spring', stiffness: 300, damping: 20 }}
            >
              <UploadCloud size={36} strokeWidth={1.5} />
            </motion.div>
            <div className="dropzone__text-group">
              <p className="dropzone__text">{t('import.dropzone')}</p>
              <p className="dropzone__hint">.xlsx · .xls · .csv · .json · .txt · .tsv</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {importProgress?.status !== 'idle' && (
          <motion.div
            className={`dropzone-progress dropzone-progress--${importProgress.status}`}
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            role="status"
            aria-live="polite"
          >
            <div className="dropzone-progress__header">
              <span className="dropzone-progress__state-icon" aria-hidden="true">
                {importProgress.status === 'completed' ? (
                  <Check size={16} />
                ) : importProgress.status === 'failed' ? (
                  <AlertCircle size={16} />
                ) : (
                  <LoaderCircle size={16} className="dropzone-progress__spinner" />
                )}
              </span>
              <div className="dropzone-progress__copy">
                <strong>{progressMessage}</strong>
                <span>{importProgress.filename}</span>
              </div>
              <strong className="dropzone-progress__percent">{progress}%</strong>
              {importBusy && (
                <button
                  type="button"
                  className="dropzone-progress__cancel"
                  onClick={clearFile}
                  title={t('import.progress.cancel')}
                  aria-label={`${t('import.progress.cancel')} ${importProgress.filename}`}
                >
                  <X size={14} />
                </button>
              )}
            </div>
            <div
              className="dropzone-progress__track"
              role="progressbar"
              aria-label={t('import.progress.label')}
              aria-valuemin="0"
              aria-valuemax="100"
              aria-valuenow={progress}
            >
              <motion.div
                className="dropzone-progress__fill"
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.3, ease: 'easeOut' }}
              />
            </div>
            <div className="dropzone-progress__steps" aria-hidden="true">
              {[
                ['reading', 1, t('import.progress.step.read')],
                ['analyzing', 24, t('import.progress.step.analyze')],
                ['importing', 68, t('import.progress.step.import')],
                ['completed', 100, t('import.progress.step.ready')],
              ].map(([phase, threshold, label]) => {
                const active =
                  importProgress.status === 'running' &&
                  (importProgress.phase === phase ||
                    (phase === 'analyzing' && importProgress.phase === 'mapping') ||
                    (phase === 'importing' && importProgress.phase === 'validating'));
                const complete =
                  progress >= threshold &&
                  !active &&
                  !(phase === 'importing' && importProgress.phase === 'mapping-required') &&
                  (phase !== 'completed' || importProgress.phase === 'completed');
                return (
                  <span
                    key={phase}
                    className={`dropzone-progress__step ${complete ? 'is-complete' : ''} ${active ? 'is-active' : ''}`}
                  >
                    <i>{complete ? <Check size={10} /> : null}</i>
                    {label}
                  </span>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── Action buttons ─── */}
      <div className="dropzone__actions">
        <button className="btn btn--primary" onClick={onBrowse} disabled={loading || importBusy}>
          <UploadCloud size={16} />
          {t('import.browse')}
        </button>
        <button className="btn btn--ghost" onClick={loadSample} disabled={loading || importBusy}>
          <FlaskConical size={16} />
          {t('import.sample')}
        </button>
      </div>
    </div>
  );
}

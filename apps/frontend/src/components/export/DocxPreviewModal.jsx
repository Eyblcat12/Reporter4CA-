/* ═══════════════════════════════════════════════════════════
   DocxPreviewModal — Full-screen DOCX preview (print preview style)
   Uses docx-preview library to render DOCX → HTML in browser
   ═══════════════════════════════════════════════════════════ */
import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  ZoomIn,
  ZoomOut,
  Download,
  FileText,
  Save,
  Loader2,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Clock3,
} from 'lucide-react';
import { useReporterContext } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import './DocxPreviewModal.css';

export default function DocxPreviewModal() {
  const {
    showPreview,
    previewBlob,
    closePreview,
    generateReport,
    savePreviewAsTemplate,
    loading,
    previewState = { status: 'none', progress: 0 },
    previewDocx = () => Promise.resolve(),
    cancelPreview = () => Promise.resolve(),
    documentRevision = 0,
  } = useReporterContext();
  const { t } = useI18n();
  const containerRef = useRef(null);
  const renderGenerationRef = useRef(0);
  const [zoom, setZoom] = useState(100);
  const [rendering, setRendering] = useState(false);
  const [showSaveForm, setShowSaveForm] = useState(false);
  const [templateName, setTemplateName] = useState('');

  useEffect(() => {
    if (!showPreview || !previewBlob || !containerRef.current) return;

    let cancelled = false;
    const generation = renderGenerationRef.current + 1;
    renderGenerationRef.current = generation;
    setRendering(true);

    (async () => {
      try {
        // Dynamic import for code splitting
        const { renderAsync } = await import('docx-preview');
        if (cancelled) return;

        // Render off-DOM. React StrictMode may start the effect twice; rendering
        // directly into the visible node lets the stale invocation append a
        // second copy of the document on top of the current one.
        const staging = document.createElement('div');
        await renderAsync(previewBlob, staging, null, {
          className: 'docx-preview-page',
          inWrapper: true,
          ignoreWidth: false,
          ignoreHeight: false,
          renderHeaders: true,
          renderFooters: true,
          renderFootnotes: true,
          renderEndnotes: true,
        });
        if (cancelled || generation !== renderGenerationRef.current || !containerRef.current)
          return;
        containerRef.current.replaceChildren(...staging.childNodes);
      } catch (err) {
        console.error('DOCX render error:', err);
        if (!cancelled && generation === renderGenerationRef.current && containerRef.current) {
          containerRef.current.replaceChildren();
          const errorBox = document.createElement('div');
          errorBox.className = 'docx-preview-error';
          errorBox.textContent = `Không thể render preview: ${err.message}`;
          containerRef.current.appendChild(errorBox);
        }
      } finally {
        if (!cancelled && generation === renderGenerationRef.current) setRendering(false);
      }
    })();

    return () => {
      cancelled = true;
      if (renderGenerationRef.current === generation) renderGenerationRef.current += 1;
    };
  }, [showPreview, previewBlob]);

  useEffect(() => {
    setZoom(100);
  }, [previewBlob]);

  const handleZoomIn = () => setZoom((z) => Math.min(z + 15, 200));
  const handleZoomOut = () => setZoom((z) => Math.max(z - 15, 50));

  const handleGenerate = () => {
    if (previewState.status !== 'current') {
      previewDocx().catch(() => {
        /* handled in context */
      });
      return;
    }
    generateReport().catch(() => {
      /* handled in context */
    });
    closePreview();
  };

  const statusView = {
    none: {
      icon: FileText,
      title: 'Chưa có Preview',
      detail: 'Tạo Preview để kiểm tra báo cáo trước khi xuất.',
    },
    generating: {
      icon: Loader2,
      title: 'Đang tạo Preview',
      detail: 'Bạn có thể đóng cửa sổ; job vẫn tiếp tục.',
    },
    current: {
      icon: CheckCircle2,
      title: 'Preview hiện hành',
      detail: 'Generate sẽ dùng lại chính DOCX đang xem.',
    },
    stale: {
      icon: AlertTriangle,
      title: 'Preview đã cũ',
      detail: 'Dữ liệu hoặc cấu hình đã thay đổi.',
    },
    expired: {
      icon: Clock3,
      title: 'Preview đã hết hạn',
      detail: 'Artifact cục bộ đã được dọn an toàn.',
    },
    failed: {
      icon: AlertTriangle,
      title: 'Preview thất bại',
      detail: previewState.errorMessage || 'Không có artifact nào được phát hành.',
    },
  }[previewState.status] || { icon: AlertTriangle, title: 'Preview chưa sẵn sàng', detail: '' };
  const StatusIcon = statusView.icon;
  const canSaveTemplate =
    Boolean(previewBlob) && ['current', 'stale'].includes(previewState.status);

  const handleSaveAsTemplate = async () => {
    if (!templateName.trim()) return;
    const saved = await savePreviewAsTemplate(templateName.trim());
    if (saved) {
      setShowSaveForm(false);
      setTemplateName('');
    }
  };

  if (!showPreview) return null;

  return (
    <AnimatePresence>
      <motion.div
        className="docx-modal__overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={closePreview}
      >
        <motion.div
          className="docx-modal"
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="docx-modal__header">
            <div className="docx-modal__title-area">
              <FileText size={18} className="docx-modal__icon" />
              <h2 className="docx-modal__title">{t('preview.title')}</h2>
            </div>

            <div className="docx-modal__controls">
              <button className="docx-modal__ctrl-btn" onClick={handleZoomOut} title="Zoom Out">
                <ZoomOut size={16} />
              </button>
              <span className="docx-modal__zoom-label">{zoom}%</span>
              <button className="docx-modal__ctrl-btn" onClick={handleZoomIn} title="Zoom In">
                <ZoomIn size={16} />
              </button>
              <button className="docx-modal__close" onClick={closePreview}>
                <X size={18} />
              </button>
            </div>
          </div>

          {/* Body */}
          <div className="docx-modal__body">
            <div className="docx-modal__document-pane">
              {(rendering || previewState.status === 'generating') && (
                <div className="docx-modal__loading">
                  <Loader2 size={24} className="docx-modal__spinner" />
                  <span>
                    {previewState.status === 'generating'
                      ? `Đang tạo Preview · ${previewState.progress || 0}%`
                      : t('preview.rendering') || 'Đang render...'}
                  </span>
                </div>
              )}
              <div
                ref={containerRef}
                className="docx-modal__container"
                style={{ transform: `scale(${zoom / 100})`, transformOrigin: 'top center' }}
              />
            </div>
            <aside className={`docx-modal__status docx-modal__status--${previewState.status}`}>
              <div className="docx-modal__status-heading">
                <span className="docx-modal__status-icon">
                  <StatusIcon size={18} />
                </span>
                <div>
                  <strong>{statusView.title}</strong>
                  <p>{statusView.detail}</p>
                </div>
              </div>
              <div className="docx-modal__progress">
                <span style={{ width: `${previewState.progress || 0}%` }} />
              </div>
              <dl className="docx-modal__status-meta">
                <div>
                  <dt>Revision</dt>
                  <dd>
                    #{documentRevision} · {previewState.status}
                  </dd>
                </div>
                <div>
                  <dt>Cache</dt>
                  <dd>{previewState.cacheMode || 'pending'}</dd>
                </div>
                <div>
                  <dt>Phase</dt>
                  <dd>{previewState.phase || '—'}</dd>
                </div>
                <div>
                  <dt>Signature</dt>
                  <dd>
                    <code>
                      {previewState.signature ? `${previewState.signature.slice(0, 8)}…` : '—'}
                    </code>
                  </dd>
                </div>
              </dl>
              {previewState.status === 'generating' && previewState.previewId && (
                <button className="btn btn--ghost btn--sm" onClick={() => cancelPreview()}>
                  <X size={14} /> Hủy Preview
                </button>
              )}
              {['stale', 'expired', 'failed'].includes(previewState.status) && (
                <button className="btn btn--ghost btn--sm" onClick={() => previewDocx()}>
                  <RefreshCw size={14} /> Tạo Preview mới
                </button>
              )}
            </aside>
          </div>

          {/* Footer */}
          <div className="docx-modal__footer">
            <div className="docx-modal__footer-left">
              {showSaveForm ? (
                <div className="docx-modal__save-form">
                  <input
                    className="docx-modal__save-input"
                    type="text"
                    placeholder="Tên template..."
                    value={templateName}
                    onChange={(e) => setTemplateName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSaveAsTemplate()}
                    autoFocus
                  />
                  <button
                    className="btn btn--ghost btn--sm"
                    onClick={handleSaveAsTemplate}
                    disabled={!templateName.trim()}
                  >
                    <Save size={14} />
                    {t('common.save')}
                  </button>
                  <button className="btn btn--ghost btn--sm" onClick={() => setShowSaveForm(false)}>
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <button
                  className="btn btn--ghost btn--sm"
                  onClick={() => setShowSaveForm(true)}
                  disabled={!canSaveTemplate}
                >
                  <Save size={14} />
                  {t('preview.saveAsTemplate') || 'Lưu làm template'}
                </button>
              )}
            </div>

            <div className="docx-modal__footer-right">
              <button className="btn btn--ghost" onClick={closePreview}>
                {t('common.close')}
              </button>
              <button className="btn btn--primary" onClick={handleGenerate} disabled={loading}>
                {previewState.status === 'current' ? (
                  <Download size={16} />
                ) : (
                  <RefreshCw size={16} />
                )}
                {previewState.status === 'current' ? 'Generate từ Preview này' : 'Tạo Preview mới'}
              </button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

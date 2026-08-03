import { useEffect, useRef, useState } from 'react';
import { FileText, Loader2 } from 'lucide-react';

export default function TemplateThumbnail({ template }) {
  const hostRef = useRef(null);
  const renderRef = useRef(null);
  const [visible, setVisible] = useState(false);
  const [status, setStatus] = useState('idle');

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;
    const observer = new IntersectionObserver(
      ([entry]) => entry.isIntersecting && setVisible(true),
      { rootMargin: '160px' },
    );
    observer.observe(host);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!visible || !template?.id || !renderRef.current) return undefined;
    const controller = new AbortController();
    let cancelled = false;
    setStatus('loading');

    (async () => {
      try {
        const [response, preview] = await Promise.all([
          fetch(`/api/templates/${template.id}/content`, { signal: controller.signal }),
          import('docx-preview'),
        ]);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const blob = await response.blob();
        if (cancelled || !renderRef.current) return;
        renderRef.current.replaceChildren();
        await preview.renderAsync(blob, renderRef.current, null, {
          className: 'tpl-thumb-docx',
          inWrapper: true,
          renderHeaders: true,
          renderFooters: false,
          renderFootnotes: false,
          renderEndnotes: false,
          breakPages: true,
        });
        if (!cancelled) setStatus('ready');
      } catch (error) {
        if (!cancelled && error.name !== 'AbortError') setStatus('error');
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [visible, template?.id, template?.fileHash]);

  return (
    <div ref={hostRef} className={`tpl-thumb tpl-thumb--${status}`} aria-label={`Preview ${template?.name || ''}`}>
      {(status === 'idle' || status === 'loading') && <Loader2 size={18} className="tpl-thumb__spinner" />}
      {status === 'error' && <FileText size={22} />}
      <div ref={renderRef} className="tpl-thumb__render" />
    </div>
  );
}

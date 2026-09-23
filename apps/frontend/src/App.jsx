/* ═══════════════════════════════════════════════════════════
   App — Root component
   ═══════════════════════════════════════════════════════════ */
import { lazy, Suspense, useEffect, useState } from 'react';
import { ThemeProvider } from './hooks/useTheme';
import { I18nProvider } from './i18n';
import { ReporterProvider } from './hooks/useReporter';
import { ToastProvider } from './components/shared/Toast';
import AppShell from './components/layout/AppShell';
import CommandPalette from './components/shared/CommandPalette';
import KeyboardShortcuts from './components/shared/KeyboardShortcuts';
import ReportJobPanel from './components/shared/ReportJobPanel';
import RuntimeLifecycle from './components/shared/RuntimeLifecycle';

const TemplateStudioRoute = lazy(
  () => import('./features/template-studio/TemplateStudioRoute.jsx'),
);
const TemplateStudioNext = lazy(
  () => import('./features/template-studio-next/TemplateStudioNext.jsx'),
);

export function isTemplateStudioNextView({ search = window.location.search } = {}) {
  return new URLSearchParams(search).get('view') === 'template-studio-next';
}

export function isTemplateStudioView({ search = window.location.search } = {}) {
  return new URLSearchParams(search).get('view') === 'template-studio';
}

function App() {
  const [templateStudio, setTemplateStudio] = useState(isTemplateStudioView);
  const [studioVisited, setStudioVisited] = useState(isTemplateStudioView);
  const [studioNext, setStudioNext] = useState(isTemplateStudioNextView);
  const [nextVisited, setNextVisited] = useState(isTemplateStudioNextView);
  useEffect(() => {
    const sync = () => {
      const studio = isTemplateStudioView();
      setTemplateStudio(studio);
      const next = isTemplateStudioNextView();
      setStudioNext(next);
      if (next) setNextVisited(true);
      if (studio) setStudioVisited(true);
    };
    window.addEventListener('popstate', sync);
    return () => window.removeEventListener('popstate', sync);
  }, []);
  function navigate(event, studio, next = false) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)
      return;
    event.preventDefault();
    const url = new URL(window.location.href);
    if (next) url.searchParams.set('view', 'template-studio-next');
    else if (studio) url.searchParams.set('view', 'template-studio');
    else url.searchParams.delete('view');
    window.history.pushState(null, '', url);
    setTemplateStudio(studio);
    setStudioNext(next);
    if (next) setNextVisited(true);
    if (studio) setStudioVisited(true);
  }

  return (
    <ThemeProvider>
      <I18nProvider defaultLocale="vi">
        <ReporterProvider>
          <ToastProvider>
            <div hidden={templateStudio || studioNext}>
              <AppShell onOpenStudio={(event) => navigate(event, true)} />
            </div>
            {studioVisited && (
              <div hidden={!templateStudio}>
                <div style={{ padding: '6px 16px', fontSize: 12 }}>
                  <a
                    href="?view=template-studio-next"
                    onClick={(event) => navigate(event, false, true)}
                  >
                    So sánh UI mới (dữ liệu mẫu)
                  </a>
                </div>
                <Suspense
                  fallback={<div className="ts-route-loading">Đang mở Template Studio…</div>}
                >
                  <TemplateStudioRoute onReturn={(event) => navigate(event, false)} />
                </Suspense>
              </div>
            )}
            {nextVisited && (
              <div hidden={!studioNext}>
                <Suspense fallback={<div>Đang mở UI so sánh…</div>}>
                  <TemplateStudioNext
                    onCompare={(event) => navigate(event, true)}
                    onReturn={(event) => navigate(event, false)}
                  />
                </Suspense>
              </div>
            )}
            {!templateStudio && !studioNext && (
              <>
                <CommandPalette />
                <KeyboardShortcuts />
              </>
            )}
            <ReportJobPanel />
            <RuntimeLifecycle />
          </ToastProvider>
        </ReporterProvider>
      </I18nProvider>
    </ThemeProvider>
  );
}

export default App;

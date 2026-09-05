/* ═══════════════════════════════════════════════════════════
   App — Root component
   ═══════════════════════════════════════════════════════════ */
import { lazy, Suspense } from 'react';
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

const TEMPLATE_STUDIO_UI_ENABLED = import.meta.env.VITE_TEMPLATE_STUDIO === '1';

export function isTemplateStudioView({
  enabled = TEMPLATE_STUDIO_UI_ENABLED,
  search = window.location.search,
} = {}) {
  return enabled && new URLSearchParams(search).get('view') === 'template-studio';
}

function App() {
  const templateStudio = isTemplateStudioView();

  return (
    <ThemeProvider>
      <I18nProvider defaultLocale="vi">
        {templateStudio ? (
          <Suspense fallback={<div className="ts-route-loading">Đang mở Template Studio…</div>}>
            <TemplateStudioRoute />
          </Suspense>
        ) : (
          <ReporterProvider>
            <ToastProvider>
              <AppShell />
              <CommandPalette />
              <KeyboardShortcuts />
              <ReportJobPanel />
              <RuntimeLifecycle />
            </ToastProvider>
          </ReporterProvider>
        )}
      </I18nProvider>
    </ThemeProvider>
  );
}

export default App;

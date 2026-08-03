/* ═══════════════════════════════════════════════════════════
   App — Root component
   ═══════════════════════════════════════════════════════════ */
import { ThemeProvider } from './hooks/useTheme';
import { I18nProvider } from './i18n';
import { ReporterProvider } from './hooks/useReporter';
import { ToastProvider } from './components/shared/Toast';
import AppShell from './components/layout/AppShell';
import CommandPalette from './components/shared/CommandPalette';
import KeyboardShortcuts from './components/shared/KeyboardShortcuts';
import ReportJobPanel from './components/shared/ReportJobPanel';
import RuntimeLifecycle from './components/shared/RuntimeLifecycle';

function App() {
  return (
    <ThemeProvider>
      <I18nProvider defaultLocale="vi">
        <ReporterProvider>
          <ToastProvider>
            <AppShell />
            <CommandPalette />
            <KeyboardShortcuts />
            <ReportJobPanel />
            <RuntimeLifecycle />
          </ToastProvider>
        </ReporterProvider>
      </I18nProvider>
    </ThemeProvider>
  );
}

export default App;

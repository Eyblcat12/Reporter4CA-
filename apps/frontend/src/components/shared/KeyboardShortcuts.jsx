/* ═══════════════════════════════════════════════════════════
   KeyboardShortcuts — Global keyboard shortcut handler
   Invisible component that registers and handles shortcuts
   ═══════════════════════════════════════════════════════════ */
import { useEffect, useCallback } from 'react';
import { useReporterContext } from '../../hooks/useReporter';

export default function KeyboardShortcuts() {
  const {
    setStep, currentStep, generateReport,
    previewDocx, rows, loading,
  } = useReporterContext();

  const handleKeyDown = useCallback((e) => {
    // Don't trigger shortcuts when typing in inputs
    const tag = e.target.tagName;
    const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target.isContentEditable;

    // Ctrl+K is handled by CommandPalette component
    // These are additional shortcuts

    if (e.ctrlKey || e.metaKey) {
      switch (e.key) {
        case '1':
          e.preventDefault();
          setStep(1);
          break;
        case '2':
          e.preventDefault();
          setStep(2);
          break;
        case '3':
          e.preventDefault();
          setStep(3);
          break;
        case 'Enter':
          if (!isInput && currentStep === 3 && rows?.length > 0 && !loading) {
            e.preventDefault();
            generateReport();
          }
          break;
        case 'p':
        case 'P':
          if (!isInput && currentStep === 3 && rows?.length > 0 && !loading) {
            e.preventDefault();
            previewDocx?.();
          }
          break;
        default:
          break;
      }
    }

    // ? key to show help (no modifier, not in input)
    if (e.key === '?' && !isInput && !e.ctrlKey && !e.metaKey && !e.altKey) {
      // Could dispatch a help modal event in the future
    }
  }, [setStep, currentStep, generateReport, previewDocx, rows, loading]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // This component renders nothing
  return null;
}

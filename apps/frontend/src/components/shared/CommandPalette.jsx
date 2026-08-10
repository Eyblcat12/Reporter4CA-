/**
 * CommandPalette.jsx
 * ──────────────────────────────────────────────────────────────
 * Premium command palette (Ctrl+K / ⌘K) for Reporter Pro.
 * Features glassmorphism overlay, fuzzy search, full keyboard
 * navigation, grouped commands, and framer-motion animations.
 * ──────────────────────────────────────────────────────────────
 */

import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Search,
  Upload,
  Settings,
  FileOutput,
  FlaskConical,
  Zap,
  Eye,
  Moon,
  Sun,
  Languages,
  CornerDownLeft,
  ArrowUp,
  ArrowDown,
} from 'lucide-react';

import { useReporterContext } from '../../hooks/useReporter';
import { useTheme } from '../../hooks/useTheme';
import { useI18n } from '../../i18n';
import './CommandPalette.css';

/* ─── Animation Variants ─────────────────────────────────── */

const overlayVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.18, ease: 'easeOut' } },
  exit: { opacity: 0, transition: { duration: 0.12, ease: 'easeIn' } },
};

const dialogVariants = {
  hidden: { opacity: 0, scale: 0.96, y: -8 },
  visible: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: { duration: 0.2, ease: [0.16, 1, 0.3, 1] },
  },
  exit: {
    opacity: 0,
    scale: 0.96,
    y: -4,
    transition: { duration: 0.12, ease: 'easeIn' },
  },
};

const itemVariants = {
  hidden: { opacity: 0, x: -4 },
  visible: (i) => ({
    opacity: 1,
    x: 0,
    transition: { delay: i * 0.02, duration: 0.15, ease: 'easeOut' },
  }),
};

/* ─── Fuzzy Match Helper ─────────────────────────────────── */

function fuzzyMatch(query, text) {
  const lowerQuery = query.toLowerCase();
  const lowerText = text.toLowerCase();

  // Direct substring match gets priority
  if (lowerText.includes(lowerQuery)) return true;

  // Character-by-character fuzzy match
  let qi = 0;
  for (let ti = 0; ti < lowerText.length && qi < lowerQuery.length; ti++) {
    if (lowerText[ti] === lowerQuery[qi]) qi++;
  }
  return qi === lowerQuery.length;
}

/* ─── Component ──────────────────────────────────────────── */

function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);

  const inputRef = useRef(null);
  const listRef = useRef(null);
  const itemRefs = useRef([]);

  // Context hooks
  const { setStep, loadSample, generateReport, previewDocx } = useReporterContext();
  const { theme, toggleTheme } = useTheme();
  const { t, locale, setLocale } = useI18n();

  // Language toggle cycles through available locales
  const toggleLang = useCallback(() => {
    setLocale(locale === 'vi' ? 'en' : 'vi');
  }, [locale, setLocale]);

  /* ─── Command Definitions ──────────────────────────────── */

  const COMMAND_GROUPS = useMemo(
    () => [
      {
        label: t('commandPalette.groupNavigation', 'Navigation'),
        commands: [
          {
            id: 'goto-import',
            icon: Upload,
            title: t('commandPalette.goToImport', 'Go to Import'),
            description: t('commandPalette.goToImportDesc', 'Navigate to data import step'),
            shortcut: 'Ctrl+1',
            action: () => setStep(1),
          },
          {
            id: 'goto-configure',
            icon: Settings,
            title: t('commandPalette.goToConfigure', 'Go to Configure'),
            description: t('commandPalette.goToConfigureDesc', 'Navigate to configuration step'),
            shortcut: 'Ctrl+2',
            action: () => setStep(2),
          },
          {
            id: 'goto-export',
            icon: FileOutput,
            title: t('commandPalette.goToExport', 'Go to Export'),
            description: t('commandPalette.goToExportDesc', 'Navigate to export step'),
            shortcut: 'Ctrl+3',
            action: () => setStep(3),
          },
        ],
      },
      {
        label: t('commandPalette.groupActions', 'Actions'),
        commands: [
          {
            id: 'load-sample',
            icon: FlaskConical,
            title: t('commandPalette.loadSample', 'Load Sample Data'),
            description: t('commandPalette.loadSampleDesc', 'Load demo dataset for testing'),
            action: () => loadSample(),
          },
          {
            id: 'generate',
            icon: Zap,
            title: t('commandPalette.generate', 'Generate Report'),
            description: t('commandPalette.generateDesc', 'Build the final report document'),
            shortcut: 'Ctrl+Enter',
            action: () => generateReport(),
          },
          {
            id: 'preview',
            icon: Eye,
            title: t('commandPalette.preview', 'Preview Report'),
            description: t('commandPalette.previewDesc', 'Open a live preview of the report'),
            shortcut: 'Ctrl+P',
            action: () => previewDocx(),
          },
        ],
      },
      {
        label: t('commandPalette.groupSettings', 'Settings'),
        commands: [
          {
            id: 'toggle-theme',
            icon: theme === 'dark' ? Sun : Moon,
            title: t('commandPalette.toggleTheme', 'Toggle Theme'),
            description:
              theme === 'dark'
                ? t('commandPalette.switchToLight', 'Switch to light mode')
                : t('commandPalette.switchToDark', 'Switch to dark mode'),
            action: toggleTheme,
          },
          {
            id: 'switch-lang',
            icon: Languages,
            title: t('commandPalette.switchLang', 'Switch Language'),
            description:
              locale === 'vi'
                ? t('commandPalette.switchToEn', 'Switch to English')
                : t('commandPalette.switchToVi', 'Chuyển sang Tiếng Việt'),
            action: toggleLang,
          },
        ],
      },
    ],
    [t, theme, locale, setStep, loadSample, generateReport, previewDocx, toggleTheme, toggleLang],
  );

  /* ─── Filtered Commands (Fuzzy Search) ─────────────────── */

  const filteredGroups = useMemo(() => {
    if (!query.trim()) return COMMAND_GROUPS;

    return COMMAND_GROUPS.map((group) => ({
      ...group,
      commands: group.commands.filter((cmd) => fuzzyMatch(query, cmd.title)),
    })).filter((group) => group.commands.length > 0);
  }, [query, COMMAND_GROUPS]);

  // Flat list of all visible commands for keyboard navigation
  const flatCommands = useMemo(() => filteredGroups.flatMap((g) => g.commands), [filteredGroups]);

  /* ─── Open / Close Handlers ────────────────────────────── */

  const close = useCallback(() => {
    setIsOpen(false);
    setQuery('');
    setSelectedIndex(0);
  }, []);

  const executeCommand = useCallback(
    (cmd) => {
      close();
      // Small delay so the palette animates out before action fires
      requestAnimationFrame(() => cmd.action());
    },
    [close],
  );

  /* ─── Global Keyboard Shortcut (Ctrl+K / ⌘K) ──────────── */

  useEffect(() => {
    function handleGlobalKeyDown(e) {
      const isMac = navigator.platform.toUpperCase().includes('MAC');
      const modifier = isMac ? e.metaKey : e.ctrlKey;

      if (modifier && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        e.stopPropagation();
        setIsOpen((prev) => !prev);
        if (!isOpen) {
          setQuery('');
          setSelectedIndex(0);
        }
      }
    }

    window.addEventListener('keydown', handleGlobalKeyDown, true);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown, true);
  }, [isOpen]);

  /* ─── Focus Input When Opened ──────────────────────────── */

  useEffect(() => {
    if (isOpen && inputRef.current) {
      // Tiny delay to allow framer-motion to mount the element
      const raf = requestAnimationFrame(() => inputRef.current?.focus());
      return () => cancelAnimationFrame(raf);
    }
  }, [isOpen]);

  /* ─── Reset Selection When Query Changes ───────────────── */

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  /* ─── Scroll Selected Item Into View ───────────────────── */

  useEffect(() => {
    const el = itemRefs.current[selectedIndex];
    if (el) {
      el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [selectedIndex]);

  /* ─── Internal Keyboard Navigation ─────────────────────── */

  function handleKeyDown(e) {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex((prev) => (prev < flatCommands.length - 1 ? prev + 1 : 0));
        break;

      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : flatCommands.length - 1));
        break;

      case 'Enter':
        e.preventDefault();
        if (flatCommands[selectedIndex]) {
          executeCommand(flatCommands[selectedIndex]);
        }
        break;

      case 'Escape':
        e.preventDefault();
        close();
        break;

      default:
        break;
    }
  }

  /* ─── Build Flat Index For Selected State ──────────────── */

  let runningIndex = 0;

  /* ─── Render ───────────────────────────────────────────── */

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="cmd-overlay"
          variants={overlayVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          onClick={close}
          aria-label={t('commandPalette.ariaOverlay', 'Command palette overlay')}
        >
          {/* ─── Dialog ─────────────────────────────────── */}
          <motion.div
            className="cmd-dialog"
            variants={dialogVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label={t('commandPalette.ariaDialog', 'Command palette')}
            onKeyDown={handleKeyDown}
          >
            {/* ─── Search Input ─────────────────────────── */}
            <div className="cmd-search">
              <Search className="cmd-search__icon" size={20} strokeWidth={2} />
              <input
                ref={inputRef}
                className="cmd-search__input"
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t('commandPalette.placeholder', 'Type a command or search…')}
                aria-label={t('commandPalette.ariaSearch', 'Search commands')}
                autoComplete="off"
                spellCheck="false"
              />
              <kbd className="cmd-kbd cmd-kbd--subtle">Esc</kbd>
            </div>

            {/* ─── Command List ─────────────────────────── */}
            <div className="cmd-list" ref={listRef} role="listbox">
              {filteredGroups.length === 0 && (
                <div className="cmd-empty">
                  <span className="cmd-empty__icon">🔍</span>
                  <p className="cmd-empty__text">
                    {t('commandPalette.noResults', 'No commands found')}
                  </p>
                  <p className="cmd-empty__hint">
                    {t('commandPalette.noResultsHint', 'Try a different search term')}
                  </p>
                </div>
              )}

              {filteredGroups.map((group) => (
                <div className="cmd-group" key={group.label}>
                  <div className="cmd-group__header">{group.label}</div>

                  {group.commands.map((cmd) => {
                    const idx = runningIndex++;
                    const isSelected = idx === selectedIndex;
                    const Icon = cmd.icon;

                    return (
                      <motion.button
                        key={cmd.id}
                        ref={(el) => {
                          itemRefs.current[idx] = el;
                        }}
                        className={`cmd-item ${isSelected ? 'cmd-item--selected' : ''}`}
                        role="option"
                        aria-selected={isSelected}
                        variants={itemVariants}
                        custom={idx}
                        initial="hidden"
                        animate="visible"
                        onClick={() => executeCommand(cmd)}
                        onMouseEnter={() => setSelectedIndex(idx)}
                      >
                        <span className="cmd-item__icon">
                          <Icon size={18} strokeWidth={1.8} />
                        </span>

                        <span className="cmd-item__body">
                          <span className="cmd-item__title">{cmd.title}</span>
                          {cmd.description && (
                            <span className="cmd-item__desc">{cmd.description}</span>
                          )}
                        </span>

                        {cmd.shortcut && <kbd className="cmd-kbd">{cmd.shortcut}</kbd>}
                      </motion.button>
                    );
                  })}
                </div>
              ))}
            </div>

            {/* ─── Footer Hints ─────────────────────────── */}
            <div className="cmd-footer">
              <span className="cmd-footer__hint">
                <kbd className="cmd-kbd cmd-kbd--tiny">
                  <ArrowUp size={11} />
                </kbd>
                <kbd className="cmd-kbd cmd-kbd--tiny">
                  <ArrowDown size={11} />
                </kbd>
                <span>{t('commandPalette.navigate', 'Navigate')}</span>
              </span>
              <span className="cmd-footer__hint">
                <kbd className="cmd-kbd cmd-kbd--tiny">
                  <CornerDownLeft size={11} />
                </kbd>
                <span>{t('commandPalette.select', 'Select')}</span>
              </span>
              <span className="cmd-footer__hint">
                <kbd className="cmd-kbd cmd-kbd--tiny">Esc</kbd>
                <span>{t('commandPalette.close', 'Close')}</span>
              </span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default CommandPalette;

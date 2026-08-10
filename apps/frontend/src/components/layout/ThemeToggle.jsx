import { Moon, Sun } from 'lucide-react';
import { useTheme } from '../../hooks/useTheme';
import './ThemeToggle.css';

export default function ThemeToggle({ compact }) {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      className={`theme-toggle ${compact ? 'theme-toggle--compact' : ''}`}
      onClick={toggleTheme}
      data-tooltip={compact ? (theme === 'dark' ? 'Light' : 'Dark') : undefined}
      aria-label="Toggle theme"
    >
      <div className="theme-toggle__icon">
        {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
      </div>
      {!compact && (
        <span className="theme-toggle__label">{theme === 'dark' ? 'Light' : 'Dark'}</span>
      )}
    </button>
  );
}

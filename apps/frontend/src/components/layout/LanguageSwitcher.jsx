import { Globe } from 'lucide-react';
import { useI18n } from '../../i18n';
import './LanguageSwitcher.css';

export default function LanguageSwitcher({ compact }) {
  const { locale, setLocale } = useI18n();

  const toggle = () => setLocale(locale === 'vi' ? 'en' : 'vi');

  return (
    <button
      className={`lang-switch ${compact ? 'lang-switch--compact' : ''}`}
      onClick={toggle}
      data-tooltip={compact ? (locale === 'vi' ? 'EN' : 'VI') : undefined}
      aria-label="Switch language"
    >
      <div className="lang-switch__icon">
        <Globe size={16} />
      </div>
      {!compact && (
        <span className="lang-switch__label">
          {locale === 'vi' ? '🇻🇳 Tiếng Việt' : '🇬🇧 English'}
        </span>
      )}
    </button>
  );
}

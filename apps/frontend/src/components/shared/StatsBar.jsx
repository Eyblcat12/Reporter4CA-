/* ═══════════════════════════════════════════════════════════
   StatsBar — Premium animated counters with radial progress
   ═══════════════════════════════════════════════════════════ */
import { motion } from 'framer-motion';
import { Server, Monitor, Layers } from 'lucide-react';
import { useReporterContext } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import './StatsBar.css';

const STATS = [
  {
    key: 'servers',
    icon: Server,
    labelKey: 'common.servers',
    color: '#60a5fa',
    gradient: 'linear-gradient(135deg, #3b82f6, #60a5fa)',
  },
  {
    key: 'clients',
    icon: Monitor,
    labelKey: 'common.clients',
    color: '#34d399',
    gradient: 'linear-gradient(135deg, #059669, #34d399)',
  },
  {
    key: 'total',
    icon: Layers,
    labelKey: 'common.total',
    color: '#a78bfa',
    gradient: 'linear-gradient(135deg, #7c5bf0, #a78bfa)',
  },
];

/* SVG donut progress */
function DonutProgress({ value, max, color, size = 44 }) {
  const r = (size - 6) / 2;
  const circumference = 2 * Math.PI * r;
  const pct = max > 0 ? value / max : 0;
  const offset = circumference * (1 - pct);

  return (
    <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} className="stats-card__donut">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="var(--border-subtle)"
        strokeWidth="3"
      />
      <motion.circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="3"
        strokeLinecap="round"
        strokeDasharray={circumference}
        initial={{ strokeDashoffset: circumference }}
        animate={{ strokeDashoffset: offset }}
        transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        style={{ transformOrigin: 'center', transform: 'rotate(-90deg)' }}
      />
    </svg>
  );
}

export default function StatsBar() {
  const { counts } = useReporterContext();
  const { t } = useI18n();
  const total = counts.total || 0;

  return (
    <div className="stats-bar">
      {STATS.map((stat, idx) => {
        const Icon = stat.icon;
        const value = counts[stat.key] ?? 0;
        return (
          <motion.div
            key={stat.key}
            className="stats-card card-glass-premium"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.08 }}
            style={{ '--stat-color': stat.color, '--stat-gradient': stat.gradient }}
          >
            <div className="stats-card__visual">
              <DonutProgress value={value} max={total || 1} color={stat.color} />
              <div className="stats-card__icon-overlay">
                <Icon size={16} />
              </div>
            </div>
            <div className="stats-card__content">
              <motion.span
                className="stats-card__value"
                key={value}
                initial={{ scale: 1.3, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: 'spring', stiffness: 400 }}
              >
                {value}
              </motion.span>
              <span className="stats-card__label">{t(stat.labelKey)}</span>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}

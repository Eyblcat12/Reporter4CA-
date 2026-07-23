import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ArrowRight,
  CircleCheck,
  FileText,
  FlaskConical,
  History,
  Layers3,
  Plus,
  TrendingUp,
  Type,
  Upload,
  X,
} from 'lucide-react';
import { useReporterContext } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import './DashboardHome.css';

const PERIODS = [30, 90, 180];
const BUCKET_COUNT = 8;
const DAY_MS = 24 * 60 * 60 * 1000;

const getField = (item, camel, snake, fallback = '') => (
  item?.[camel] ?? item?.[snake] ?? fallback
);

const parseDate = (item) => {
  const value = getField(item, 'createdAt', 'created_at');
  const date = value ? new Date(value) : null;
  return date && !Number.isNaN(date.getTime()) ? date : null;
};

const reportRows = (item) => Number(getField(item, 'rowCount', 'row_count', 0)) || 0;

function buildSummary(history, days, locale) {
  const now = Date.now();
  const start = now - days * DAY_MS;
  const previousStart = start - days * DAY_MS;
  const current = [];
  let previousCount = 0;

  history.forEach((item) => {
    const date = parseDate(item);
    if (!date) return;
    const timestamp = date.getTime();
    if (timestamp >= start && timestamp <= now) current.push(item);
    else if (timestamp >= previousStart && timestamp < start) previousCount += 1;
  });

  const bucketMs = (days * DAY_MS) / BUCKET_COUNT;
  const buckets = Array.from({ length: BUCKET_COUNT }, (_, index) => ({
    start: start + index * bucketMs,
    end: start + (index + 1) * bucketMs,
    count: 0,
  }));

  current.forEach((item) => {
    const timestamp = parseDate(item)?.getTime();
    if (!timestamp) return;
    const index = Math.min(BUCKET_COUNT - 1, Math.max(0, Math.floor((timestamp - start) / bucketMs)));
    buckets[index].count += 1;
  });

  const dateFormatter = new Intl.DateTimeFormat(locale === 'vi' ? 'vi-VN' : 'en-US', {
    day: days === 180 ? undefined : 'numeric',
    month: 'short',
  });

  const assets = current.reduce((sum, item) => sum + reportRows(item), 0);
  const reportTypes = new Set(
    current.map((item) => getField(item, 'reportType', 'report_type', 'full')).filter(Boolean),
  );
  const delta = previousCount > 0
    ? Math.round(((current.length - previousCount) / previousCount) * 100)
    : null;

  return {
    reports: current.length,
    assets,
    types: reportTypes.size,
    delta,
    values: buckets.map((bucket) => bucket.count),
    labels: buckets.map((bucket) => dateFormatter.format(new Date(bucket.end))),
  };
}

function ActivityChart({ values, labels, emptyLabel }) {
  const width = 640;
  const height = 250;
  const left = 52;
  const right = 626;
  const top = 24;
  const bottom = 184;
  const tickCount = 4;
  const rawMax = Math.max(4, ...values);
  const step = Math.max(1, Math.ceil(rawMax / tickCount));
  const max = step * tickCount;
  const yTicks = Array.from({ length: tickCount + 1 }, (_, index) => index * step);
  const points = values.map((value, index) => ({
    x: left + (index * (right - left)) / Math.max(1, values.length - 1),
    y: bottom - (value / max) * (bottom - top),
    value,
    label: labels[index],
  }));
  const path = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');
  const area = points.length
    ? `${path} L ${points[points.length - 1].x} ${bottom} L ${points[0].x} ${bottom} Z`
    : '';
  const total = values.reduce((sum, value) => sum + value, 0);

  return (
    <div className="dashboard-home__chart-wrap">
      <svg
        className="dashboard-home__chart"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={total > 0 ? `${total} reports across ${values.length} periods` : emptyLabel}
      >
        {yTicks.map((value) => {
          const y = bottom - (value / max) * (bottom - top);
          return (
            <g key={value}>
              <line className="dashboard-home__grid-line" x1={left} y1={y} x2={right} y2={y} />
              <text className="dashboard-home__y-axis-label" x={left - 12} y={y + 4} textAnchor="end">
                {value}
              </text>
            </g>
          );
        })}
        <path className="dashboard-home__area" d={area} />
        <path className="dashboard-home__line" d={path} />
        {points.map((point, index) => (
          <g key={`${point.label}-${index}`}>
            <circle
              className="dashboard-home__point"
              cx={point.x}
              cy={point.y}
              r={index === points.length - 1 ? 4 : 3}
            >
              <title>{`${point.label}: ${point.value}`}</title>
            </circle>
            <text className="dashboard-home__axis-label" x={point.x} y="222" textAnchor="middle">
              {point.label}
            </text>
          </g>
        ))}
      </svg>
      {total === 0 && <span className="dashboard-home__chart-empty">{emptyLabel}</span>}
    </div>
  );
}

export default function DashboardHome({ onOpenImport }) {
  const fileRef = useRef(null);
  const recentRef = useRef(null);
  const [period, setPeriod] = useState(90);
  const [launcherOpen, setLauncherOpen] = useState(false);
  const [source, setSource] = useState('file');
  const [showAll, setShowAll] = useState(false);
  const {
    importFile,
    loadSample,
    reportHistory,
    dashboardSummary,
    fetchReportHistory,
    fetchDashboardSummary,
    lastReportId,
    loading,
  } = useReporterContext();
  const { locale, t } = useI18n();

  useEffect(() => {
    fetchReportHistory();
  }, [fetchReportHistory, lastReportId]);

  useEffect(() => {
    fetchDashboardSummary(period);
  }, [fetchDashboardSummary, lastReportId, period]);

  const localSummary = useMemo(
    () => buildSummary(reportHistory || [], period, locale),
    [reportHistory, period, locale],
  );

  const summary = useMemo(() => {
    if (!dashboardSummary || dashboardSummary.days !== period) return localSummary;
    const metrics = dashboardSummary.metrics || {};
    const dateFormatter = new Intl.DateTimeFormat(locale === 'vi' ? 'vi-VN' : 'en-US', {
      day: period === 180 ? undefined : 'numeric',
      month: 'short',
    });
    const series = dashboardSummary.series || [];
    const bucketMs = (period * DAY_MS) / Math.max(1, series.length);
    return {
      reports: metrics.reports || 0,
      attempts: metrics.attempts || 0,
      assets: metrics.assets || 0,
      types: metrics.reportTypes || 0,
      successRate: metrics.successRate,
      avgDurationMs: metrics.avgDurationMs || 0,
      delta: metrics.deltaPercent,
      values: series.map((item) => item.count || 0),
      labels: series.map((item) => (
        dateFormatter.format(new Date(item.end || (new Date(item.start).getTime() + bucketMs)))
      )),
    };
  }, [dashboardSummary, localSummary, locale, period]);

  const compactRecentSource = dashboardSummary?.recent || reportHistory || [];
  const fullHistorySource = reportHistory?.length ? reportHistory : compactRecentSource;
  const recentSource = showAll ? fullHistorySource : compactRecentSource;

  const recent = useMemo(() => {
    const sorted = [...recentSource].sort((a, b) => {
      const aTime = parseDate(a)?.getTime() || 0;
      const bTime = parseDate(b)?.getTime() || 0;
      return bTime - aTime;
    });
    return showAll ? sorted : sorted.slice(0, 4);
  }, [recentSource, showAll]);

  const numberFormatter = useMemo(
    () => new Intl.NumberFormat(locale === 'vi' ? 'vi-VN' : 'en-US'),
    [locale],
  );
  const dateFormatter = useMemo(
    () => new Intl.DateTimeFormat(locale === 'vi' ? 'vi-VN' : 'en-US', { day: '2-digit', month: 'short' }),
    [locale],
  );
  const dateTimeFormatter = useMemo(
    () => new Intl.DateTimeFormat(locale === 'vi' ? 'vi-VN' : 'en-US', {
      day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    }),
    [locale],
  );

  const handleFile = (file) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => importFile(file.name, reader.result, file.size);
    reader.readAsDataURL(file);
  };

  const continueWithSource = () => {
    setLauncherOpen(false);
    if (source === 'file') {
      fileRef.current?.click();
      return;
    }
    if (source === 'text') {
      onOpenImport?.('text');
      return;
    }
    loadSample();
  };

  const revealHistory = () => {
    setShowAll(true);
    recentRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  const deltaText = summary.delta === null
    ? t('dashboard.noPrevious')
    : `${summary.delta >= 0 ? '+' : ''}${summary.delta}%`;
  const successText = summary.successRate == null ? '—' : `${summary.successRate}%`;
  const successContext = summary.attempts
    ? `${numberFormatter.format(summary.reports)}/${numberFormatter.format(summary.attempts)} ${t('dashboard.completed')}`
    : t('dashboard.noAttempts');
  const sourceDescriptions = {
    file: t('dashboard.source.fileDesc'),
    text: t('dashboard.source.textDesc'),
    sample: t('dashboard.source.sampleDesc'),
  };

  return (
    <motion.div
      className="dashboard-home"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
    >
      <input
        ref={fileRef}
        type="file"
        accept=".xlsx,.xls,.csv,.json,.txt,.tsv"
        onChange={(event) => handleFile(event.target.files?.[0])}
        hidden
      />

      <header className="dashboard-home__header">
        <div className="dashboard-home__heading">
          <h1>{t('dashboard.title')}</h1>
          <span>{t('dashboard.subtitle')}</span>
        </div>
        <div className="dashboard-home__header-actions">
          <button className="btn btn-secondary" type="button" onClick={revealHistory}>
            <History size={16} />
            {t('dashboard.history')}
          </button>
          <button
            className="btn btn-primary"
            type="button"
            onClick={() => setLauncherOpen((open) => !open)}
            aria-expanded={launcherOpen}
            aria-controls="dashboard-source-launcher"
          >
            <Plus size={16} />
            {t('dashboard.newReport')}
          </button>
        </div>
      </header>

      <AnimatePresence initial={false}>
        {launcherOpen && (
          <motion.section
            id="dashboard-source-launcher"
            className="dashboard-home__launcher card"
            initial={{ opacity: 0, height: 0, y: -8 }}
            animate={{ opacity: 1, height: 'auto', y: 0 }}
            exit={{ opacity: 0, height: 0, y: -8 }}
            transition={{ duration: 0.2 }}
          >
            <div className="dashboard-home__launcher-head">
              <div>
                <strong>{t('dashboard.chooseSource')}</strong>
                <span>{sourceDescriptions[source]}</span>
              </div>
              <button
                className="btn btn-ghost btn-icon"
                type="button"
                onClick={() => setLauncherOpen(false)}
                aria-label={t('common.close')}
              >
                <X size={16} />
              </button>
            </div>
            <div className="dashboard-home__source-row" role="group" aria-label={t('dashboard.chooseSource')}>
              {[
                { id: 'file', icon: Upload, label: t('dashboard.source.file') },
                { id: 'text', icon: Type, label: t('dashboard.source.text') },
                { id: 'sample', icon: FlaskConical, label: t('dashboard.source.sample') },
              ].map((item) => {
                const Icon = item.icon;
                const selected = source === item.id;
                return (
                  <button
                    key={item.id}
                    className={`btn ${selected ? 'btn-primary' : 'btn-secondary'}`}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => setSource(item.id)}
                  >
                    <Icon size={15} />
                    {item.label}
                  </button>
                );
              })}
              <button className="btn btn-secondary dashboard-home__continue" type="button" onClick={continueWithSource} disabled={loading}>
                {t('dashboard.continue')}
                <ArrowRight size={15} />
              </button>
            </div>
          </motion.section>
        )}
      </AnimatePresence>

      <section className="dashboard-home__kpis" aria-label={t('dashboard.metrics')}>
        <article className="dashboard-home__kpi card">
          <div className="dashboard-home__kpi-head">
            <span>{t('dashboard.reports')}</span>
            <span className="dashboard-home__delta"><TrendingUp size={14} />{deltaText}</span>
          </div>
          <strong>{numberFormatter.format(summary.reports)}</strong>
          <small>{t('dashboard.periodContext')}</small>
        </article>
        <article className="dashboard-home__kpi card">
          <div className="dashboard-home__kpi-head">
            <span>{t('dashboard.assets')}</span>
            <Layers3 size={15} />
          </div>
          <strong>{numberFormatter.format(summary.assets)}</strong>
          <small>{t('dashboard.assetsContext')}</small>
        </article>
        <article className="dashboard-home__kpi card">
          <div className="dashboard-home__kpi-head">
            <span>{t('dashboard.success')}</span>
            <CircleCheck size={15} />
          </div>
          <strong>{successText}</strong>
          <small>{successContext}</small>
        </article>
      </section>

      <div className="dashboard-home__main">
        <section className="dashboard-home__activity" aria-labelledby="dashboard-activity-title">
          <div className="dashboard-home__section-head">
            <div>
              <span id="dashboard-activity-title">{t('dashboard.activity')}</span>
              <strong>{numberFormatter.format(summary.reports)} {t('dashboard.reports').toLowerCase()}</strong>
            </div>
            <div className="dashboard-home__periods" role="group" aria-label={t('dashboard.period')}>
              {PERIODS.map((days) => (
                <button
                  key={days}
                  className={`btn btn-sm ${period === days ? 'btn-primary' : 'btn-ghost'}`}
                  type="button"
                  aria-pressed={period === days}
                  onClick={() => setPeriod(days)}
                >
                  {days === 180 ? t('dashboard.sixMonths') : `${days}d`}
                </button>
              ))}
            </div>
          </div>
          <ActivityChart values={summary.values} labels={summary.labels} emptyLabel={t('dashboard.noActivity')} />
          <div className="dashboard-home__chart-detail">
            <span />
            {t('dashboard.latestPeriod')}: {summary.values[summary.values.length - 1] || 0}
          </div>
        </section>

        <section ref={recentRef} className="dashboard-home__recent" aria-labelledby="dashboard-recent-title">
          <div className="dashboard-home__section-head">
            <span id="dashboard-recent-title">{t('dashboard.recent')}</span>
            {Math.max(compactRecentSource.length, fullHistorySource.length) > 4 && (
              <button className="btn btn-ghost btn-sm" type="button" onClick={() => setShowAll((value) => !value)}>
                {showAll ? t('dashboard.showLess') : t('dashboard.viewAll')}
              </button>
            )}
          </div>
          <div className="dashboard-home__recent-list">
            {recent.length === 0 ? (
              <div className="dashboard-home__recent-empty">
                <FileText size={18} />
                <span>{t('dashboard.noReports')}</span>
              </div>
            ) : recent.map((item) => {
              const createdAt = parseDate(item);
              const title = getField(item, 'title', 'title') || getField(item, 'outputFilename', 'output_filename') || t('dashboard.untitled');
              const type = getField(item, 'reportType', 'report_type', 'full');
              const status = getField(item, 'status', 'status', 'success');
              const failed = status === 'failed';
              const cancelled = status === 'cancelled';
              const statusLabel = failed
                ? t('dashboard.reportFailed')
                : cancelled ? t('dashboard.reportCancelled') : t('dashboard.reportSuccess');
              return (
                <article className={`dashboard-home__report ${failed ? 'dashboard-home__report--failed' : ''} ${cancelled ? 'dashboard-home__report--cancelled' : ''}`} key={getField(item, 'id', 'id', `${title}-${createdAt?.getTime()}`)}>
                  <div>
                    <strong>{title}</strong>
                    <span>
                      <i />
                      {statusLabel} · {type} · {numberFormatter.format(reportRows(item))} {t('dashboard.assets').toLowerCase()}
                    </span>
                  </div>
                  <time dateTime={createdAt?.toISOString()}>
                    {createdAt ? (showAll ? dateTimeFormatter.format(createdAt) : dateFormatter.format(createdAt)) : '—'}
                  </time>
                </article>
              );
            })}
          </div>
        </section>
      </div>

      <footer className="dashboard-home__status">
        <span />
        {t('dashboard.ready')}
      </footer>
    </motion.div>
  );
}

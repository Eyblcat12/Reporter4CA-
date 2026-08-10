/* ═══════════════════════════════════════════════════════════
   AssetTable — Premium editable data table with search
   ═══════════════════════════════════════════════════════════ */
import { useState, useMemo, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Trash2, Server, Monitor, Search, WandSparkles } from 'lucide-react';
import { useReporterContext } from '../../hooks/useReporter';
import { useI18n } from '../../i18n';
import DataQualityPanel from './DataQualityPanel';
import './AssetTable.css';

export default function AssetTable() {
  const { rows, addRow, removeRow, updateRow, dataQuality, validateRows, startRuleFromRow } =
    useReporterContext();
  const { t } = useI18n();
  const [editingCell, setEditingCell] = useState(null);
  const [search, setSearch] = useState('');
  const [qualityFilter, setQualityFilter] = useState('all');

  useEffect(() => {
    const timer = window.setTimeout(() => validateRows(rows), 250);
    return () => window.clearTimeout(timer);
  }, [rows, validateRows]);

  const counts = useMemo(() => {
    const s = rows.filter((r) => r.type === 'server').length;
    const c = rows.filter((r) => r.type === 'client').length;
    return { servers: s, clients: c, total: s + c };
  }, [rows]);

  const filteredRows = useMemo(() => {
    const issueRows = new Set(
      (dataQuality?.issues || [])
        .filter((issue) => {
          if (qualityFilter === 'all') return true;
          if (qualityFilter === 'errors') return issue.level === 'error';
          if (qualityFilter === 'warnings') return issue.level === 'warning';
          return issue.code === qualityFilter;
        })
        .map((issue) => issue.row - 1),
    );
    const q = search.toLowerCase();
    return rows
      .map((row, idx) => ({ row, idx }))
      .filter(({ idx }) => qualityFilter === 'all' || issueRows.has(idx))
      .filter(
        ({ row }) =>
          !search.trim() ||
          Object.values(row).some((v) =>
            String(v || '')
              .toLowerCase()
              .includes(q),
          ),
      );
  }, [rows, search, dataQuality, qualityFilter]);

  const handleCellClick = (rowIdx, field) => {
    setEditingCell(`${rowIdx}-${field}`);
  };

  const handleCellBlur = () => {
    setEditingCell(null);
  };

  const handleCellChange = (rowIdx, field, value) => {
    updateRow(rowIdx, { ...rows[rowIdx], [field]: value });
  };

  const revealIssue = (issue) => {
    setQualityFilter(issue.level === 'error' ? 'errors' : issue.code);
    window.setTimeout(() => {
      document
        .querySelector(`[data-row-index="${issue.row - 1}"]`)
        ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setEditingCell(`${issue.row - 1}-${issue.field}`);
    }, 0);
  };

  const applyQualityFilter = (filter) => {
    setQualityFilter(filter);
    if (filter === 'all') return;
    const issue = (dataQuality?.issues || []).find((item) =>
      filter === 'errors'
        ? item.level === 'error'
        : filter === 'warnings'
          ? item.level === 'warning'
          : item.code === filter,
    );
    if (issue) {
      window.setTimeout(() => {
        document
          .querySelector(`[data-row-index="${issue.row - 1}"]`)
          ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 0);
    }
  };

  const trimValues = () => {
    rows.forEach((row, idx) => {
      const normalized = Object.fromEntries(
        Object.entries(row).map(([key, value]) => [
          key,
          typeof value === 'string' ? value.trim() : value,
        ]),
      );
      updateRow(idx, normalized);
    });
  };

  const fillMissingResult = () => {
    rows.forEach((row, idx) => {
      if (!String(row.result || '').trim()) updateRow(idx, { ...row, result: 'Chưa đánh giá' });
    });
  };

  const renderCell = (row, rowIdx, field) => {
    const key = `${rowIdx}-${field}`;
    const isEditing = editingCell === key;
    const value = row[field] || '';

    if (isEditing) {
      return (
        <input
          className="asset-table__cell-input"
          value={value}
          onChange={(e) => handleCellChange(rowIdx, field, e.target.value)}
          onBlur={handleCellBlur}
          onKeyDown={(e) => e.key === 'Enter' && handleCellBlur()}
          autoFocus
        />
      );
    }

    return (
      <span
        className="asset-table__cell-text"
        onClick={() => handleCellClick(rowIdx, field)}
        title="Click to edit"
      >
        {value || '—'}
      </span>
    );
  };

  return (
    <div className="asset-table-wrapper">
      <DataQualityPanel
        quality={dataQuality}
        activeFilter={qualityFilter}
        onFilter={applyQualityFilter}
        onIssue={revealIssue}
        onTrimValues={trimValues}
        onFillResult={fillMissingResult}
      />
      <div className="asset-table__header">
        <div className="asset-table__search">
          <Search size={14} />
          <input
            className="asset-table__search-input"
            type="text"
            placeholder={t('common.search') || 'Tìm kiếm...'}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="asset-table__badges">
          <span className="badge badge--blue">
            <Server size={12} /> {counts.servers} {t('common.servers')}
          </span>
          <span className="badge badge--green">
            <Monitor size={12} /> {counts.clients} {t('common.clients')}
          </span>
          <span className="badge badge--purple">
            {counts.total} {t('common.total')}
          </span>
        </div>
      </div>

      <div className="asset-table__scroll">
        <table className="asset-table">
          <thead>
            <tr>
              <th className="asset-table__th--type">Type</th>
              <th>Hostname</th>
              <th>IP</th>
              <th>OS</th>
              <th>Result</th>
              <th>Notes</th>
              <th className="asset-table__th--actions"></th>
            </tr>
          </thead>
          <tbody>
            <AnimatePresence>
              {filteredRows.map(({ row, idx }) => (
                <motion.tr
                  key={`${row.hostname}-${idx}`}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ delay: Math.min(idx * 0.02, 0.5), duration: 0.2 }}
                  className={row.type === 'server' ? 'row--server' : 'row--client'}
                  data-row-index={idx}
                >
                  <td>
                    <button
                      className={`type-badge type-badge--${row.type}`}
                      onClick={() =>
                        handleCellChange(idx, 'type', row.type === 'server' ? 'client' : 'server')
                      }
                      title="Click to toggle"
                    >
                      {row.type === 'server' ? <Server size={12} /> : <Monitor size={12} />}
                      {row.type === 'server' ? 'SRV' : 'CLT'}
                    </button>
                  </td>
                  <td className="cell--hostname">{renderCell(row, idx, 'hostname')}</td>
                  <td>{renderCell(row, idx, 'ip')}</td>
                  <td>{renderCell(row, idx, 'os')}</td>
                  <td>{renderCell(row, idx, 'result')}</td>
                  <td>{renderCell(row, idx, 'notes')}</td>
                  <td>
                    <div className="asset-table__actions">
                      {(String(row.notes || '').trim() || String(row.result || '').trim()) && (
                        <button
                          className="asset-table__rule"
                          onClick={() =>
                            startRuleFromRow(
                              idx,
                              String(row.notes || '').trim() ? 'notes' : 'result',
                            )
                          }
                          title="Tạo rule từ nội dung dòng này"
                          aria-label={`Tạo rule từ ${row.hostname || `dòng ${idx + 1}`}`}
                        >
                          <WandSparkles size={14} />
                        </button>
                      )}
                      <button
                        className="asset-table__delete"
                        onClick={() => removeRow(idx)}
                        title={t('common.delete')}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </motion.tr>
              ))}
            </AnimatePresence>
          </tbody>
        </table>
      </div>

      <div className="asset-table__footer">
        <button className="btn btn--ghost btn--sm" onClick={() => addRow('server')}>
          <Plus size={14} /> <Server size={12} /> Server
        </button>
        <button className="btn btn--ghost btn--sm" onClick={() => addRow('client')}>
          <Plus size={14} /> <Monitor size={12} /> Client
        </button>
      </div>
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle, CheckCircle2, Copy, Download, FlaskConical, History, Pencil,
  Plus, Save, ShieldCheck, Sparkles, Upload, X,
} from 'lucide-react';
import { useReporterContext } from '../../hooks/useReporter';
import './RuleManager.css';

const EMPTY_RULE = {
  name: '', description: '', severity: 'medium', classification: 'needs_review',
  remediation: '', enabled: true,
  conditions: {
    fields: ['notes', 'result'], containsAny: [], containsAll: [],
    excludeContainsAny: [], regexAny: [], assetTypes: [],
  },
};

const FIELD_OPTIONS = [
  ['notes', 'Ghi chú'], ['result', 'Kết quả'], ['software', 'Phần mềm'],
  ['process', 'Tiến trình'], ['installed_software', 'Phần mềm đã cài'],
  ['hostname', 'Hostname'], ['ip', 'IP'], ['os', 'Hệ điều hành'],
];

const splitTerms = (value) => String(value || '').split(/[\n,]/).map((item) => item.trim()).filter(Boolean);

function toDraft(rule = EMPTY_RULE) {
  return {
    ...EMPTY_RULE, ...rule,
    conditions: { ...EMPTY_RULE.conditions, ...(rule.conditions || {}) },
  };
}

export default function RuleManager() {
  const {
    rows, detectionRules, fetchDetectionRules, saveDetectionRule, evaluateDetectionRule,
    fetchDetectionRuleVersions, rollbackDetectionRule,
    detectionRuleConflicts, fetchDetectionRuleConflicts, cloneDetectionRule,
    exportDetectionRules, importDetectionRules,
    reportSettings, setReportSettings,
    ruleDraftSource, clearRuleDraftSource,
  } = useReporterContext();
  const [showBuilder, setShowBuilder] = useState(false);
  const [draft, setDraft] = useState(toDraft());
  const [keywords, setKeywords] = useState('');
  const [exclusions, setExclusions] = useState('');
  const [testResult, setTestResult] = useState(null);
  const [testedSignature, setTestedSignature] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [versions, setVersions] = useState([]);
  const [teamMessage, setTeamMessage] = useState('');
  const importInputRef = useRef(null);
  const disabled = useMemo(
    () => new Set(reportSettings.ruleSettings?.disabledRuleIds || []),
    [reportSettings.ruleSettings?.disabledRuleIds],
  );

  useEffect(() => {
    fetchDetectionRules();
    fetchDetectionRuleConflicts();
  }, [fetchDetectionRules, fetchDetectionRuleConflicts]);

  useEffect(() => {
    if (!ruleDraftSource) return;
    setDraft(toDraft({
      name: `Phát hiện từ ${ruleDraftSource.hostname || `dòng ${ruleDraftSource.row + 1}`}`,
      classification: 'needs_review',
      severity: 'medium',
      conditions: { ...EMPTY_RULE.conditions, fields: [ruleDraftSource.field] },
      remediation: 'Xác minh nội dung ghi nhận, mục đích sử dụng và bằng chứng liên quan.',
    }));
    setKeywords(ruleDraftSource.value);
    setExclusions('');
    setTestResult(null);
    setTestedSignature('');
    setError('');
    setVersions([]);
    setShowBuilder(true);
    clearRuleDraftSource();
  }, [clearRuleDraftSource, ruleDraftSource]);

  const toggle = (ruleId) => {
    const next = new Set(disabled);
    if (next.has(ruleId)) next.delete(ruleId); else next.add(ruleId);
    setReportSettings({
      ...reportSettings,
      ruleSettings: { ...(reportSettings.ruleSettings || {}), disabledRuleIds: [...next] },
    });
  };

  const startNew = () => {
    setDraft(toDraft()); setKeywords(''); setExclusions('');
    setTestResult(null); setTestedSignature(''); setError(''); setVersions([]); setShowBuilder(true);
  };

  const startEdit = async (rule) => {
    setDraft(toDraft(rule));
    setKeywords((rule.conditions?.containsAny || []).join(', '));
    setExclusions((rule.conditions?.excludeContainsAny || []).join(', '));
    setTestResult(null); setTestedSignature(''); setError(''); setShowBuilder(true);
    setVersions(await fetchDetectionRuleVersions(rule.id));
  };

  const rollback = async (versionNumber) => {
    setBusy(true); setError('');
    try {
      const restored = await rollbackDetectionRule(draft.id, versionNumber);
      setDraft(toDraft(restored));
      setKeywords((restored.conditions?.containsAny || []).join(', '));
      setExclusions((restored.conditions?.excludeContainsAny || []).join(', '));
      setVersions(await fetchDetectionRuleVersions(draft.id));
      setTestResult(null); setTestedSignature('');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const buildRule = () => ({
    ...draft,
    conditions: {
      ...draft.conditions,
      containsAny: splitTerms(keywords),
      excludeContainsAny: splitTerms(exclusions),
    },
  });

  const runTest = async () => {
    setBusy(true); setError(''); setTestResult(null);
    const candidate = buildRule();
    try {
      setTestResult(await evaluateDetectionRule(candidate));
      setTestedSignature(JSON.stringify(candidate));
    }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const save = async () => {
    const candidate = buildRule();
    if (!testResult || testedSignature !== JSON.stringify(candidate)) {
      setError('Hãy chạy thử lại rule sau thay đổi trước khi lưu.');
      return;
    }
    setBusy(true); setError('');
    try {
      const saved = await saveDetectionRule(candidate);
      await fetchDetectionRuleConflicts();
      setTeamMessage(saved.applicationWarning
        ? `Đã lưu ${saved.name}; bảng phân tích sẽ được làm mới ở lần thử tiếp theo.`
        : `Đã lưu và áp dụng ${saved.name} trên ${rows.length} tài sản.`);
      setShowBuilder(false); setTestResult(null);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const cloneRule = async (ruleId) => {
    setBusy(true); setError('');
    try {
      const clone = await cloneDetectionRule(ruleId);
      setTeamMessage(`Đã nhân bản: ${clone.name}`);
      await fetchDetectionRuleConflicts();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const exportRules = async () => {
    setBusy(true); setError('');
    try {
      const bundle = await exportDetectionRules();
      const url = URL.createObjectURL(new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' }));
      const anchor = document.createElement('a');
      anchor.href = url; anchor.download = 'reporter-pro-rules.json'; anchor.click();
      URL.revokeObjectURL(url);
      setTeamMessage(`Đã xuất ${bundle.rules.length} rule tùy chỉnh.`);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const importRules = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setBusy(true); setError('');
    try {
      const bundle = JSON.parse(await file.text());
      if (!Array.isArray(bundle.rules)) throw new Error('File không có danh sách rules hợp lệ');
      const result = await importDetectionRules(bundle.rules, 'rename');
      setTeamMessage(`Đã import ${result.imported.length}; bỏ qua ${result.skipped.length}; lỗi ${result.errors.length}.`);
      await fetchDetectionRuleConflicts();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const setConditionField = (field) => {
    const fields = new Set(draft.conditions.fields || []);
    if (fields.has(field)) fields.delete(field); else fields.add(field);
    setDraft({ ...draft, conditions: { ...draft.conditions, fields: [...fields] } });
  };

  const canSave = Boolean(testResult && testedSignature === JSON.stringify(buildRule()));

  return (
    <div className="rule-manager">
      <div className="rule-manager__header">
        <div className="rule-manager__intro">
          <ShieldCheck size={17} />
          <span>Rule chỉ kết luận khi có bằng chứng khớp trong dữ liệu đầu vào.</span>
        </div>
        <div className="rule-manager__toolbar">
          <button type="button" onClick={exportRules} disabled={busy}><Download size={14} /> Export</button>
          <button type="button" onClick={() => importInputRef.current?.click()} disabled={busy}><Upload size={14} /> Import</button>
          <input ref={importInputRef} type="file" accept="application/json,.json" hidden onChange={importRules} />
        <button type="button" className="rule-manager__add" onClick={startNew}>
          <Plus size={14} /> Thêm rule
        </button>
        </div>
      </div>

      {teamMessage && <p className="rule-manager__message">{teamMessage}</p>}
      {(detectionRuleConflicts || []).length > 0 && (
        <div className="rule-conflicts">
          <AlertTriangle size={15} />
          <span>
            <strong>{detectionRuleConflicts.length} rule chồng lấn.</strong>
            {(detectionRuleConflicts || []).slice(0, 3).map((item) => (
              <small key={item.ruleIds.join(':')}>
                {item.ruleNames?.join(' ↔ ') || item.ruleIds.join(' ↔ ')}
                {' · '}{item.sharedTerms.join(', ')}
                {item.classificationConflict ? ' · khác kết luận' : ''}
              </small>
            ))}
          </span>
        </div>
      )}

      {showBuilder && (
        <section className="rule-builder" aria-label="Tạo rule phát hiện">
          <div className="rule-builder__title">
            <div><strong>{draft.id ? 'Chỉnh sửa rule' : 'Rule mới'}</strong><small>Chạy thử trên dữ liệu hiện tại trước khi lưu và áp dụng.</small></div>
            <button type="button" aria-label="Đóng" onClick={() => setShowBuilder(false)}><X size={16} /></button>
          </div>
          <div className="rule-builder__grid">
            <label>Tên rule<input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder="Ví dụ: Phát hiện công cụ proxy nội bộ" /></label>
            <label>Phân loại<select value={draft.classification} onChange={(e) => setDraft({ ...draft, classification: e.target.value })}><option value="needs_review">Cần xác minh</option><option value="anomaly">Bất thường</option><option value="insufficient_data">Chưa đủ dữ liệu</option><option value="informational">Thông tin</option></select></label>
            <label>Mức độ<select value={draft.severity} onChange={(e) => setDraft({ ...draft, severity: e.target.value })}><option value="informational">Thông tin</option><option value="low">Thấp</option><option value="medium">Trung bình</option><option value="high">Cao</option><option value="critical">Nghiêm trọng</option></select></label>
          </div>
          <fieldset className="rule-builder__fields"><legend>Tìm trong trường</legend>{FIELD_OPTIONS.map(([value, label]) => <label key={value}><input type="checkbox" checked={draft.conditions.fields.includes(value)} onChange={() => setConditionField(value)} />{label}</label>)}</fieldset>
          <div className="rule-builder__grid rule-builder__grid--two">
            <label>Từ khóa cần khớp<textarea value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="proxifier, tor browser, vpn client" /><small>Phân tách bằng dấu phẩy hoặc xuống dòng; chỉ cần khớp một từ.</small></label>
            <label>Loại trừ khi có<textarea value={exclusions} onChange={(e) => setExclusions(e.target.value)} placeholder="được phê duyệt, hợp lệ, authorized" /><small>Giúp tránh cảnh báo nhầm từ nội dung phủ định hoặc đã xác minh.</small></label>
          </div>
          <label>Hướng xử lý<input value={draft.remediation} onChange={(e) => setDraft({ ...draft, remediation: e.target.value })} placeholder="Xác minh mục đích và phê duyệt sử dụng" /></label>
          {error && <p className="rule-builder__error">{error}</p>}
          {testResult && (
            <div className="rule-test">
              <div className="rule-test__summary">
                <span><Sparkles size={13} /><b>{testResult.matchedRows}</b> khớp</span>
                <span><CheckCircle2 size={13} /><b>{testResult.changedRows}</b> đổi kết luận</span>
                <span><b>{testResult.impact?.servers || 0}</b> server · <b>{testResult.impact?.clients || 0}</b> client</span>
              </div>
              {(testResult.conflicts || []).length > 0 && (
                <p className="rule-test__warning">
                  <AlertTriangle size={13} /> Rule nháp chồng lấn với {testResult.conflicts.length} rule hiện có.
                </p>
              )}
              {testResult.matches.length ? (
                <ul>{testResult.matches.slice(0, 12).map((match) => (
                  <li key={`${match.row}-${match.hostname}`}>
                    <b>Dòng {match.row + 1} · {match.hostname || 'Chưa có hostname'}</b>
                    <span>{match.assessmentBefore} → {match.assessmentAfter}</span>
                    <small>{match.evidence.map((item) => `${item.field}: ${item.matched}`).join('; ')}</small>
                  </li>
                ))}</ul>
              ) : <span>Không có dòng nào khớp. Rule này sẽ không tạo finding.</span>}
              {testResult.truncated && <small>Chỉ hiển thị 100 kết quả đầu tiên.</small>}
            </div>
          )}
          {draft.id && versions.length > 0 && <div className="rule-versions"><strong><History size={13} /> Lịch sử phiên bản</strong><div>{versions.map((item, index) => <span key={item.id}><b>v{item.versionNumber}</b><small>{new Date(item.createdAt).toLocaleString()}</small>{index > 0 && <button type="button" disabled={busy} onClick={() => rollback(item.versionNumber)}>Khôi phục</button>}</span>)}</div></div>}
          <div className="rule-builder__actions">
            <button type="button" onClick={runTest} disabled={busy || !rows?.length}><FlaskConical size={14} /> Thử trên {rows?.length || 0} dòng</button>
            <button type="button" className="primary" onClick={save} disabled={busy || !canSave}><Save size={14} /> Lưu & áp dụng</button>
          </div>
        </section>
      )}

      <div className="rule-manager__list">
        {(detectionRules || []).map((rule) => {
          const enabled = !disabled.has(rule.id);
          return (
            <div className="rule-manager__item" key={rule.id}>
              <label className="rule-manager__toggle">
                <input aria-label={`Bật ${rule.name}`} type="checkbox" checked={enabled} onChange={() => toggle(rule.id)} />
                <span className="rule-manager__switch" />
              </label>
              <span className="rule-manager__content">
                <strong>{rule.name}</strong>
                <small>{rule.source === 'custom' ? 'Tùy chỉnh' : 'Mặc định'} · {rule.severity} · {rule.classification}</small>
                <em>{rule.remediation || rule.description}</em>
              </span>
              <button type="button" className="rule-manager__clone" aria-label={`Clone ${rule.name}`} onClick={() => cloneRule(rule.id)}><Copy size={14} /></button>
              {rule.editable && <button type="button" className="rule-manager__edit" aria-label={`Sửa ${rule.name}`} onClick={() => startEdit(rule)}><Pencil size={14} /></button>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

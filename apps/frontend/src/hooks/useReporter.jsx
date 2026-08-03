/* ═══════════════════════════════════════════════════════════
   useReporter — Main state management hook
   ═══════════════════════════════════════════════════════════ */
import { createContext, useContext, useReducer, useCallback, useEffect, useRef } from 'react';

const ReporterContext = createContext(null);

const initialState = {
  currentStep: 1,
  rows: [],
  payload: null,
  counts: { servers: 0, clients: 0, total: 0 },
  reportSettings: {
    title: 'BÁO CÁO ĐÁNH GIÁ AN TOÀN THÔNG TIN',
    organization: '',
    assessmentDate: new Date().toISOString().split('T')[0],
    templatePath: '',
    reportType: 'full',
    pluginsDir: '',
    disablePlugins: false,
    ruleSettings: { disabledRuleIds: [] },
    outputName: '',
    incidentMetadata: {
      incidentId: '', severity: 'High', status: 'Đang xử lý', detectedAt: '',
      executiveSummary: '', containmentActions: '', eradicationActions: '',
      recoveryActions: '', lessonsLearned: '', timelineText: '', iocsText: '',
      timeline: [], iocs: [],
    },
  },
  columnMapping: null,
  columnPreview: null,
  importedFile: null,
  importedFileData: null,
  previewText: '',
  logs: [],
  loading: false,
  error: null,
  templates: [],
  presets: [],
  previewBlob: null,
  previewSignature: '',
  documentRevision: 0,
  previewState: {
    status: 'none', previewId: '', jobId: '', sequence: 0, revision: -1,
    progress: 0, phase: '', signature: '', templateHash: '', expiresAt: '',
    cacheMode: '', errorCode: '', errorMessage: '',
  },
  showPreview: false,
  lastReportId: null,
  reportHistory: [],
  dashboardSummary: null,
  dataQuality: { valid: true, issues: [], summary: null },
  reportJobs: [],
  activeReportJob: null,
  detectionRules: [],
  detectionRuleConflicts: [],
  ruleDraftSource: null,
};

function recountRows(rows) {
  const servers = rows.filter((r) => r.type === 'server').length;
  const clients = rows.filter((r) => r.type === 'client').length;
  return { servers, clients, total: rows.length };
}

function withDocumentChange(state, changes) {
  const previewState = state.previewState.status === 'current'
    ? { ...state.previewState, status: 'stale' }
    : state.previewState;
  return {
    ...state,
    ...changes,
    documentRevision: state.documentRevision + 1,
    previewState,
  };
}

export function normalizeIncidentMetadata(metadata = {}) {
  const parseLines = (value, keys) => String(value || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const parts = line.split('|').map((part) => part.trim());
      return Object.fromEntries(keys.map((key, index) => [key, parts[index] || '']));
    });

  return {
    ...metadata,
    timeline: parseLines(metadata.timelineText, ['time', 'event', 'evidence', 'relatedIocs']),
    iocs: parseLines(metadata.iocsText, ['type', 'value', 'source']),
    containmentActions: parseLines(metadata.containmentActions, ['action', 'status', 'owner', 'evidence']),
    eradicationActions: parseLines(metadata.eradicationActions, ['action', 'status', 'owner', 'evidence']),
    recoveryActions: parseLines(metadata.recoveryActions, ['action', 'status', 'owner', 'evidence']),
  };
}

export function validateIncidentMetadata(metadata = {}) {
  const data = normalizeIncidentMetadata(metadata);
  const errors = [];
  const warnings = [];
  const add = (target, code, field, message, row) => target.push({ code, field, message, ...(row ? { row } : {}) });
  const text = (value) => String(value || '').trim();

  if (!text(data.incidentId)) add(errors, 'missing_incident_id', 'incidentId', 'Chưa có mã sự cố.');
  if (!text(data.detectedAt)) add(errors, 'missing_detected_at', 'detectedAt', 'Chưa có thời điểm phát hiện.');
  if (!data.timeline.length) add(errors, 'missing_timeline', 'timeline', 'Timeline phải có ít nhất một sự kiện.');

  const knownIocs = new Set(data.iocs.map((ioc) => text(ioc.value)).filter(Boolean));
  const evidence = new Set();
  data.timeline.forEach((event, index) => {
    if (!text(event.event)) add(errors, 'missing_timeline_event', 'timeline', 'Sự kiện timeline chưa có mô tả.', index + 1);
    if (!text(event.time)) add(warnings, 'missing_timeline_time', 'timeline', 'Sự kiện timeline chưa có thời gian.', index + 1);
    if (text(event.evidence)) evidence.add(text(event.evidence));
    else add(warnings, 'missing_timeline_evidence', 'timeline', 'Sự kiện timeline chưa liên kết evidence.', index + 1);
    text(event.relatedIocs).split(',').map((value) => value.trim()).filter(Boolean).forEach((value) => {
      if (!knownIocs.has(value)) add(warnings, 'unknown_related_ioc', 'timeline', `IoC liên quan '${value}' chưa có trong danh sách IoC.`, index + 1);
    });
  });
  data.iocs.forEach((ioc, index) => {
    if (!text(ioc.type) || !text(ioc.value)) add(errors, 'invalid_ioc', 'iocs', 'IoC phải có cả loại và giá trị.', index + 1);
    if (text(ioc.source)) evidence.add(text(ioc.source));
    else add(warnings, 'missing_ioc_source', 'iocs', 'IoC chưa có nguồn evidence.', index + 1);
  });

  let actions = 0;
  let completedActions = 0;
  [['containmentActions', 'khoanh vùng'], ['eradicationActions', 'loại bỏ'], ['recoveryActions', 'khôi phục']]
    .forEach(([field, label]) => {
      data[field].forEach((action, index) => {
        actions += 1;
        if (!text(action.action)) add(errors, 'missing_action', field, `Hành động ${label} chưa có mô tả.`, index + 1);
        if (['done', 'completed', 'complete', 'đã hoàn thành', 'hoàn thành'].includes(text(action.status).toLowerCase())) completedActions += 1;
        if (!text(action.owner)) add(warnings, 'missing_action_owner', field, `Hành động ${label} chưa có người phụ trách.`, index + 1);
        if (text(action.evidence)) evidence.add(text(action.evidence));
        else add(warnings, 'missing_action_evidence', field, `Hành động ${label} chưa liên kết evidence.`, index + 1);
      });
    });

  return {
    valid: errors.length === 0,
    errors,
    warnings,
    summary: {
      timelineEvents: data.timeline.length,
      iocs: data.iocs.length,
      actions,
      completedActions,
      evidenceReferences: evidence.size,
      errors: errors.length,
      warnings: warnings.length,
    },
  };
}

function reducer(state, action) {
  switch (action.type) {
    case 'SET_STEP':
      return { ...state, currentStep: action.payload };
    case 'SET_LOADING':
      return { ...state, loading: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload };
    case 'SET_ROWS': {
      const rows = action.payload;
      return withDocumentChange(state, { rows, counts: recountRows(rows) });
    }
    case 'ADD_ROW': {
      const rows = [...state.rows, action.payload];
      return withDocumentChange(state, { rows, counts: recountRows(rows) });
    }
    case 'REMOVE_ROW': {
      const rows = state.rows.filter((_, i) => i !== action.payload);
      return withDocumentChange(state, { rows, counts: recountRows(rows) });
    }
    case 'UPDATE_ROW': {
      const rows = [...state.rows];
      rows[action.payload.index] = action.payload.data;
      return withDocumentChange(state, { rows, counts: recountRows(rows) });
    }
    case 'SET_PAYLOAD':
      return { ...state, payload: action.payload };
    case 'SET_REPORT_SETTINGS':
      return withDocumentChange(state, { reportSettings: action.payload });
    case 'SET_COLUMN_MAPPING':
      return { ...state, columnMapping: action.payload };
    case 'SET_COLUMN_PREVIEW':
      return { ...state, columnPreview: action.payload };
    case 'SET_IMPORTED_FILE':
      return { ...state, importedFile: action.payload };
    case 'SET_IMPORTED_FILE_DATA':
      return { ...state, importedFileData: action.payload };
    case 'SET_PREVIEW_TEXT':
      return { ...state, previewText: action.payload };
    case 'ADD_LOG':
      return { ...state, logs: [...state.logs, `[${new Date().toLocaleTimeString()}] ${action.payload}`] };
    case 'SET_TEMPLATES':
      return { ...state, templates: action.payload };
    case 'SET_PRESETS':
      return { ...state, presets: action.payload };
    case 'SET_PREVIEW_BLOB':
      return { ...state, previewBlob: action.payload };
    case 'SET_PREVIEW_SIGNATURE':
      return { ...state, previewSignature: action.payload };
    case 'SET_PREVIEW_STATE':
      if ((action.payload.sequence || 0) < (state.previewState.sequence || 0)) return state;
      return { ...state, previewState: { ...state.previewState, ...action.payload } };
    case 'UPDATE_PREVIEW_JOB':
      if (action.payload.sequence !== state.previewState.sequence) return state;
      return { ...state, previewState: { ...state.previewState, ...action.payload.data } };
    case 'PREVIEW_READY':
      if (action.payload.sequence !== state.previewState.sequence) return state;
      return {
        ...state,
        previewBlob: action.payload.blob,
        previewSignature: action.payload.signature,
        previewState: {
          ...state.previewState,
          ...action.payload.data,
          status: action.payload.revision === state.documentRevision ? 'current' : 'stale',
          revision: action.payload.revision,
          progress: 100,
          phase: 'completed',
        },
      };
    case 'SET_SHOW_PREVIEW':
      return { ...state, showPreview: action.payload };
    case 'SET_LAST_REPORT_ID':
      return { ...state, lastReportId: action.payload };
    case 'SET_REPORT_HISTORY':
      return { ...state, reportHistory: action.payload };
    case 'SET_DASHBOARD_SUMMARY':
      return { ...state, dashboardSummary: action.payload };
    case 'SET_DATA_QUALITY':
      return { ...state, dataQuality: action.payload };
    case 'SET_REPORT_JOBS':
      return { ...state, reportJobs: action.payload };
    case 'SET_ACTIVE_REPORT_JOB':
      return { ...state, activeReportJob: action.payload };
    case 'SET_DETECTION_RULES':
      return { ...state, detectionRules: action.payload };
    case 'SET_DETECTION_RULE_CONFLICTS':
      return { ...state, detectionRuleConflicts: action.payload };
    case 'SET_RULE_DRAFT_SOURCE':
      return { ...state, ruleDraftSource: action.payload };
    default:
      return state;
  }
}

const API_BASE = '/api';

export function ReporterProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const importRequestRef = useRef({ id: 0, controller: null });
  const previewRequestRef = useRef(null);
  const previewSequenceRef = useRef(0);
  const documentRevisionRef = useRef(0);
  const jobPollRef = useRef({ id: null, stopped: false });

  useEffect(() => {
    documentRevisionRef.current = state.documentRevision;
  }, [state.documentRevision]);

  const addLog = useCallback((msg) => {
    dispatch({ type: 'ADD_LOG', payload: msg });
  }, []);

  const setStep = useCallback((step) => {
    dispatch({ type: 'SET_STEP', payload: step });
  }, []);

  const setReportSettings = useCallback((settings) => {
    dispatch({ type: 'SET_REPORT_SETTINGS', payload: settings });
  }, []);

  const setColumnMapping = useCallback((mapping) => {
    dispatch({ type: 'SET_COLUMN_MAPPING', payload: mapping });
  }, []);

  const addRow = useCallback((type = 'server') => {
    dispatch({
      type: 'ADD_ROW',
      payload: { type, hostname: '', ip: '', os: '', result: '', notes: '' },
    });
  }, []);

  const removeRow = useCallback((index) => {
    dispatch({ type: 'REMOVE_ROW', payload: index });
  }, []);

  const updateRow = useCallback((index, data) => {
    dispatch({ type: 'UPDATE_ROW', payload: { index, data } });
  }, []);

  const startRuleFromRow = useCallback((index, field = 'notes') => {
    const row = state.rows[index];
    const value = String(row?.[field] || '').trim();
    if (!row || !value) return false;
    dispatch({
      type: 'SET_RULE_DRAFT_SOURCE',
      payload: { row: index, field, value, hostname: row.hostname || '', type: row.type || 'client' },
    });
    dispatch({ type: 'SET_STEP', payload: 2 });
    addLog(`Tạo rule nháp từ ${field} của ${row.hostname || `dòng ${index + 1}`}`);
    return true;
  }, [addLog, state.rows]);

  const clearRuleDraftSource = useCallback(() => {
    dispatch({ type: 'SET_RULE_DRAFT_SOURCE', payload: null });
  }, []);

  // Fetch templates
  const fetchTemplates = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/templates`);
      if (res.ok) {
        const data = await res.json();
        dispatch({ type: 'SET_TEMPLATES', payload: data.templates || [] });
      }
    } catch (err) {
      console.warn('Could not load templates:', err);
    }
  }, []);

  // Import file — sends base64 to backend, gets column preview first
  const importFile = useCallback(async (filename, dataUrl, fileSize = 0) => {
    importRequestRef.current.controller?.abort();
    const requestId = importRequestRef.current.id + 1;
    const controller = new AbortController();
    importRequestRef.current = { id: requestId, controller };
    dispatch({ type: 'SET_ERROR', payload: null });
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_IMPORTED_FILE', payload: { name: filename, size: fileSize } });
    dispatch({ type: 'SET_IMPORTED_FILE_DATA', payload: dataUrl });
    addLog(`Uploading: ${filename}`);

    try {
      // Step 1: Column preview
      const previewRes = await fetch(`${API_BASE}/column-preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename, contentBase64: dataUrl }),
        signal: controller.signal,
      });

      if (!previewRes.ok) {
        const err = await previewRes.json().catch(() => ({}));
        throw new Error(err.detail || `Preview error: ${previewRes.status}`);
      }

      const preview = await previewRes.json();
      if (requestId !== importRequestRef.current.id) return;
      dispatch({ type: 'SET_COLUMN_PREVIEW', payload: preview });
      dispatch({ type: 'SET_COLUMN_MAPPING', payload: preview.suggestedMapping || {} });
      addLog(`Detected ${(preview.columns || []).length} columns`);

      // Step 2: Auto-import with suggested mapping (if mapping has hostname)
      const mapping = preview.suggestedMapping || {};
      const hasHostname = Object.values(mapping).some(v =>
        ['hostname', 'hostname_server', 'hostname_client'].includes(v)
      );

      if (hasHostname) {
        const importRes = await fetch(`${API_BASE}/import-file`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            filename,
            contentBase64: dataUrl,
            defaultType: 'client',
            columnMapping: mapping,
            sheetName: preview.sheets?.[0] || '',
            headerRow: preview.headerRow || 0,
          }),
          signal: controller.signal,
        });

        if (!importRes.ok) {
          const error = await importRes.json().catch(() => ({}));
          throw new Error(error.detail || `Import error: ${importRes.status}`);
        }
        const data = await importRes.json();
        if (requestId !== importRequestRef.current.id) return;
        if (data.rows && data.rows.length > 0) {
          dispatch({ type: 'SET_ROWS', payload: data.rows });
          dispatch({ type: 'SET_PAYLOAD', payload: data.payload || data });
          dispatch({ type: 'SET_PREVIEW_TEXT', payload: data.previewText || '' });
          addLog(`Import thành công: ${data.rows.length} dòng (${data.counts?.servers || 0} server, ${data.counts?.clients || 0} client)`);
        } else {
          addLog('Cảnh báo: Không có dữ liệu sau import. Hãy kiểm tra ánh xạ cột.');
        }
      } else {
        addLog('Hãy ánh xạ cột Hostname ở bước ② rồi nhấn "Áp dụng"');
      }
    } catch (err) {
      if (err.name === 'AbortError') return;
      dispatch({ type: 'SET_ERROR', payload: err.message });
      addLog(`Error: ${err.message}`);
    } finally {
      if (requestId === importRequestRef.current.id) {
        dispatch({ type: 'SET_LOADING', payload: false });
      }
    }
  }, [addLog]);

  // Apply column mapping — re-import with user mapping
  const applyColumnMapping = useCallback(async () => {
    if (!state.importedFile || !state.importedFileData) {
      addLog('Lỗi: Không tìm thấy dữ liệu file. Hãy import lại file.');
      return;
    }
    dispatch({ type: 'SET_LOADING', payload: true });
    addLog('Đang áp dụng ánh xạ cột...');

    try {
      const importRes = await fetch(`${API_BASE}/import-file`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: state.importedFile.name,
          contentBase64: state.importedFileData,
          defaultType: 'client',
          columnMapping: state.columnMapping,
          sheetName: state.columnPreview?.sheets?.[0] || '',
          headerRow: state.columnPreview?.headerRow || 0,
        }),
      });

      if (!importRes.ok) {
        const err = await importRes.json().catch(() => ({}));
        throw new Error(err.detail || `Lỗi ánh xạ cột: ${importRes.status}`);
      }

      const data = await importRes.json();
      if (data.rows && data.rows.length > 0) {
        dispatch({ type: 'SET_ROWS', payload: data.rows });
        dispatch({ type: 'SET_PAYLOAD', payload: data.payload || data });
        dispatch({ type: 'SET_PREVIEW_TEXT', payload: data.previewText || '' });
        addLog(`Ánh xạ thành công! ${data.rows.length} dòng dữ liệu (${data.counts?.servers || 0} server, ${data.counts?.clients || 0} client)`);
      } else {
        addLog('Cảnh báo: Không có dữ liệu nào sau khi ánh xạ. Kiểm tra lại mapping cột.');
      }
    } catch (err) {
      dispatch({ type: 'SET_ERROR', payload: err.message });
      addLog(`Lỗi ánh xạ: ${err.message}`);
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [state.importedFile, state.importedFileData, state.columnMapping, state.columnPreview, addLog]);

  // Normalize raw text
  const normalizeRaw = useCallback(async (text, defaultType = 'client') => {
    dispatch({ type: 'SET_ERROR', payload: null });
    dispatch({ type: 'SET_LOADING', payload: true });
    addLog(`Normalizing raw text (${defaultType})...`);

    try {
      const res = await fetch(`${API_BASE}/normalize-raw`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rawText: text, defaultType }),
      });
      if (!res.ok) throw new Error(`Normalize error: ${res.status}`);

      const data = await res.json();
      const rows = data.rows || [];
      dispatch({ type: 'SET_ROWS', payload: [...state.rows, ...rows] });
      dispatch({ type: 'SET_PAYLOAD', payload: data.payload || data });
      dispatch({ type: 'SET_PREVIEW_TEXT', payload: data.previewText || '' });
      addLog(`Normalized ${rows.length} entries`);
    } catch (err) {
      dispatch({ type: 'SET_ERROR', payload: err.message });
      addLog(`Error: ${err.message}`);
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [state.rows, addLog]);

  // Load sample
  const loadSample = useCallback(async () => {
    dispatch({ type: 'SET_ERROR', payload: null });
    dispatch({ type: 'SET_LOADING', payload: true });
    addLog('Loading sample data...');

    try {
      const res = await fetch(`${API_BASE}/sample`);
      if (!res.ok) throw new Error(`Sample error: ${res.status}`);

      const data = await res.json();
      dispatch({ type: 'SET_ROWS', payload: data.rows || [] });
      dispatch({ type: 'SET_PAYLOAD', payload: data.payload || data });
      dispatch({ type: 'SET_PREVIEW_TEXT', payload: data.previewText || '' });
      addLog(`Loaded ${(data.rows || []).length} sample rows`);
    } catch (err) {
      dispatch({ type: 'SET_ERROR', payload: err.message });
      addLog(`Error: ${err.message}`);
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [addLog]);

  const validateRows = useCallback(async (rows = state.rows) => {
    if (!rows?.length) {
      const empty = { valid: true, issues: [], summary: null };
      dispatch({ type: 'SET_DATA_QUALITY', payload: empty });
      return empty;
    }
    try {
      const res = await fetch(`${API_BASE}/validate-rows`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows }),
      });
      if (!res.ok) throw new Error(`Validation error: ${res.status}`);
      const result = await res.json();
      dispatch({ type: 'SET_DATA_QUALITY', payload: result });
      return result;
    } catch (err) {
      console.warn('Could not validate rows:', err);
      return null;
    }
  }, [state.rows]);

  const downloadReportJob = useCallback(async (job) => {
    const res = await fetch(`${API_BASE}/report-jobs/${job.id}/download`);
    if (!res.ok) throw new Error(`Download error: ${res.status}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = job.filename || 'reporter-output.docx';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    if (job.reportId) dispatch({ type: 'SET_LAST_REPORT_ID', payload: job.reportId });
    addLog(`Report downloaded: ${anchor.download}`);
  }, [addLog]);

  const monitorReportJob = useCallback(async (jobId) => {
    jobPollRef.current = { id: jobId, stopped: false };
    let consecutiveFailures = 0;
    while (!jobPollRef.current.stopped && jobPollRef.current.id === jobId) {
      let data;
      try {
        const res = await fetch(`${API_BASE}/report-jobs/${jobId}`);
        if (!res.ok) throw new Error(`Job status error: ${res.status}`);
        data = await res.json();
        consecutiveFailures = 0;
      } catch (error) {
        consecutiveFailures += 1;
        if (consecutiveFailures > 3) {
          dispatch({
            type: 'SET_ACTIVE_REPORT_JOB',
            payload: { id: jobId, status: 'unavailable', phase: 'recovery', errorMessage: error.message },
          });
          throw new Error(`Không thể cập nhật tiến độ job sau 3 lần thử lại: ${error.message}`);
        }
        addLog(`Mất kết nối tiến độ job, đang thử lại (${consecutiveFailures}/3)...`);
        await new Promise((resolve) => window.setTimeout(resolve, 750));
        continue;
      }
      const job = data.job;
      dispatch({ type: 'SET_ACTIVE_REPORT_JOB', payload: job });
      if (job.status === 'completed') {
        if (job.reportId) dispatch({ type: 'SET_LAST_REPORT_ID', payload: job.reportId });
        await downloadReportJob(job);
        return job;
      }
      if (job.status === 'failed') throw new Error(job.errorMessage || 'Report job failed');
      if (job.status === 'cancelled') {
        addLog('Report job cancelled');
        return job;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 750));
    }
    return null;
  }, [addLog, downloadReportJob]);

  const cancelReportJob = useCallback(async (jobId) => {
    const res = await fetch(`${API_BASE}/report-jobs/${jobId}`, { method: 'DELETE' });
    if (!res.ok) return false;
    const data = await res.json();
    dispatch({ type: 'SET_ACTIVE_REPORT_JOB', payload: data.job });
    return true;
  }, []);

  const fetchReportJobs = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/report-jobs`);
      if (!res.ok) return [];
      const data = await res.json();
      dispatch({ type: 'SET_REPORT_JOBS', payload: data.jobs || [] });
      return data.jobs || [];
    } catch {
      return [];
    }
  }, []);

  // Generate DOCX as a bounded local background job.
  const generateReport = useCallback(async () => {
    if (['queued', 'running'].includes(state.activeReportJob?.status)) {
      addLog('A report job is already active');
      return state.activeReportJob;
    }
    dispatch({ type: 'SET_ERROR', payload: null });
    dispatch({ type: 'SET_LOADING', payload: true });
    addLog('Queueing DOCX report...');

    try {
      const quality = await validateRows(state.rows);
      if (quality && !quality.valid) {
        throw new Error('Dữ liệu còn lỗi nghiêm trọng. Hãy sửa trước khi tạo báo cáo.');
      }
      const reportMetadata = state.reportSettings.reportType === 'incident_response'
        ? normalizeIncidentMetadata(state.reportSettings.incidentMetadata)
        : {};
      if (state.reportSettings.reportType === 'incident_response') {
        const incidentQuality = validateIncidentMetadata(reportMetadata);
        if (!incidentQuality.valid) {
          throw new Error(`Thông tin Incident Response còn ${incidentQuality.errors.length} lỗi nghiêm trọng.`);
        }
        reportMetadata.incidentQuality = incidentQuality.summary;
      }
      const body = {
        rows: state.rows,
        title: state.reportSettings.title,
        organization: state.reportSettings.organization,
        assessmentDate: state.reportSettings.assessmentDate,
        templatePath: state.reportSettings.templatePath,
        reportType: state.reportSettings.reportType,
        disablePlugins: state.reportSettings.disablePlugins,
        outputName: state.reportSettings.outputName || 'reporter-output',
        clientRequestId: globalThis.crypto?.randomUUID?.() || `report-${Date.now()}`,
        ...(state.previewState.status === 'current'
          && state.previewState.revision === state.documentRevision
          && state.previewState.previewId
          ? { previewId: state.previewState.previewId }
          : {}),
        metadata: {
          ...reportMetadata,
          ruleSettings: state.reportSettings.ruleSettings,
          dataQuality: quality?.summary || state.dataQuality.summary,
        },
      };

      const res = await fetch(`${API_BASE}/report-jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Queue error: ${res.status}`);
      }
      const data = await res.json();
      const job = data.job;
      dispatch({ type: 'SET_ACTIVE_REPORT_JOB', payload: job });
      dispatch({ type: 'SET_LOADING', payload: false });
      if (body.previewId) addLog('Reusing verified Preview artifact');
      else addLog(data.deduplicated ? 'Reopened existing report job' : 'Generating fresh report');
      return await monitorReportJob(job.id);
    } catch (err) {
      dispatch({ type: 'SET_ERROR', payload: err.message });
      addLog(`Error: ${err.message}`);
      throw err;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [state.rows, state.reportSettings, state.dataQuality.summary, state.activeReportJob,
    state.previewState, state.documentRevision, addLog, validateRows, monitorReportJob]);

  // ── Presets ──────────────────────────────────────────────

  const fetchPresets = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/presets`);
      if (res.ok) {
        const data = await res.json();
        dispatch({ type: 'SET_PRESETS', payload: data.presets || [] });
      }
    } catch (err) {
      console.warn('Could not load presets:', err);
    }
  }, []);

  const savePreset = useCallback(async (name, description = '') => {
    try {
      const res = await fetch(`${API_BASE}/presets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          description,
          settings: state.reportSettings,
          columnMapping: state.columnMapping,
        }),
      });
      if (res.ok) {
        addLog(`Preset saved: ${name}`);
        await fetchPresets();
        return true;
      }
    } catch (err) {
      addLog(`Error saving preset: ${err.message}`);
    }
    return false;
  }, [state.reportSettings, state.columnMapping, addLog, fetchPresets]);

  const loadPreset = useCallback(async (presetId) => {
    try {
      const res = await fetch(`${API_BASE}/presets/${presetId}`);
      if (res.ok) {
        const preset = await res.json();
        if (preset.settings) {
          dispatch({ type: 'SET_REPORT_SETTINGS', payload: { ...state.reportSettings, ...preset.settings } });
        }
        if (preset.columnMapping) {
          dispatch({ type: 'SET_COLUMN_MAPPING', payload: preset.columnMapping });
        }
        addLog(`Preset loaded: ${preset.name}`);
        return true;
      }
    } catch (err) {
      addLog(`Error loading preset: ${err.message}`);
    }
    return false;
  }, [state.reportSettings, addLog]);

  const deletePreset = useCallback(async (presetId) => {
    try {
      const res = await fetch(`${API_BASE}/presets/${presetId}`, { method: 'DELETE' });
      if (res.ok) {
        addLog('Preset deleted');
        await fetchPresets();
        return true;
      }
    } catch (err) {
      addLog(`Error deleting preset: ${err.message}`);
    }
    return false;
  }, [addLog, fetchPresets]);

  // ── Template management ─────────────────────────────────

  const uploadTemplate = useCallback(async (
    filename, dataUrl, name = '', description = '', reportType = '', isDefault = false,
  ) => {
    dispatch({ type: 'SET_LOADING', payload: true });
    addLog(`Uploading template: ${filename}`);
    try {
      const res = await fetch(`${API_BASE}/templates/upload`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename,
          contentBase64: dataUrl,
          name,
          description,
          reportType: reportType || state.reportSettings.reportType || 'full',
          isDefault,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Upload error');
      }
      const data = await res.json();
      addLog(`Template uploaded: ${data.name}`);
      await fetchTemplates();
      return data;
    } catch (err) {
      dispatch({ type: 'SET_ERROR', payload: err.message });
      addLog(`Error: ${err.message}`);
      return null;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [addLog, fetchTemplates, state.reportSettings.reportType]);

  const updateTemplate = useCallback(async (templateId, updates) => {
    try {
      const res = await fetch(`${API_BASE}/templates/${templateId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Update template error');
      }
      await fetchTemplates();
      return true;
    } catch (err) {
      addLog(`Error: ${err.message}`);
      return false;
    }
  }, [addLog, fetchTemplates]);

  const deleteTemplate = useCallback(async (templateId) => {
    try {
      const res = await fetch(`${API_BASE}/templates/${templateId}`, { method: 'DELETE' });
      if (res.ok) {
        addLog('Template deleted');
        await fetchTemplates();
        return true;
      }
      const err = await res.json().catch(() => ({}));
      addLog(`Cannot delete: ${err.detail || 'Error'}`);
    } catch (err) {
      addLog(`Error: ${err.message}`);
    }
    return false;
  }, [addLog, fetchTemplates]);

  const analyzeTemplate = useCallback(async (templateId) => {
    try {
      const res = await fetch(`${API_BASE}/templates/${templateId}/analyze`);
      if (res.ok) return await res.json();
    } catch (err) {
      console.warn('Analyze error:', err);
    }
    return null;
  }, []);

  const fetchTemplateVersions = useCallback(async (templateId) => {
    const res = await fetch(`${API_BASE}/templates/${templateId}/versions`);
    if (!res.ok) return [];
    return (await res.json()).versions || [];
  }, []);

  const uploadTemplateVersion = useCallback(async (templateId, dataUrl, note = '') => {
    const res = await fetch(`${API_BASE}/templates/${templateId}/versions`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ contentBase64: dataUrl, note }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    await fetchTemplates();
    return data;
  }, [fetchTemplates]);

  const rollbackTemplateVersion = useCallback(async (templateId, version) => {
    const res = await fetch(`${API_BASE}/templates/${templateId}/versions/${version}/rollback`, { method: 'POST' });
    if (!res.ok) return false;
    await fetchTemplates();
    return true;
  }, [fetchTemplates]);

  const fetchDetectionRules = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/rules`);
      if (!res.ok) return [];
      const data = await res.json();
      dispatch({ type: 'SET_DETECTION_RULES', payload: data.rules || [] });
      return data.rules || [];
    } catch {
      return [];
    }
  }, []);

  const reanalyzeRows = useCallback(async () => {
    if (!state.rows.length) return null;
    const res = await fetch(`${API_BASE}/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        rows: state.rows,
        metadata: { ruleSettings: state.reportSettings.ruleSettings || {} },
        disablePlugins: true,
      }),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || 'Không thể áp dụng lại rule trên dữ liệu');
    }
    const data = await res.json();
    dispatch({ type: 'SET_ROWS', payload: data.rows || state.rows });
    dispatch({ type: 'SET_PAYLOAD', payload: data.payload || null });
    dispatch({ type: 'SET_PREVIEW_TEXT', payload: data.previewText || '' });
    addLog(`Đã phân tích lại ${data.rows?.length || state.rows.length} tài sản bằng rule hiện hành`);
    return data;
  }, [addLog, state.reportSettings.ruleSettings, state.rows]);

  const saveDetectionRule = useCallback(async (rule) => {
    const editing = Boolean(rule.id);
    const res = await fetch(`${API_BASE}/rules${editing ? `/${rule.id}` : ''}`, {
      method: editing ? 'PATCH' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rule),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || 'Không thể lưu rule');
    }
    const saved = await res.json();
    await fetchDetectionRules();
    try {
      await reanalyzeRows();
    } catch (error) {
      addLog(`Đã lưu rule nhưng chưa thể làm mới bảng phân tích: ${error.message}`);
      return { ...saved, applicationWarning: error.message };
    }
    addLog(`Đã lưu rule: ${saved.name}`);
    return saved;
  }, [addLog, fetchDetectionRules, reanalyzeRows]);

  const evaluateDetectionRule = useCallback(async (rule) => {
    const res = await fetch(`${API_BASE}/rules/evaluate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        rows: state.rows,
        rule,
        disabledRuleIds: state.reportSettings.ruleSettings?.disabledRuleIds || [],
        editingRuleId: rule.id || '',
      }),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || 'Không thể chạy thử rule');
    }
    return res.json();
  }, [state.reportSettings.ruleSettings?.disabledRuleIds, state.rows]);

  const fetchDetectionRuleVersions = useCallback(async (ruleId) => {
    const res = await fetch(`${API_BASE}/rules/${ruleId}/versions`);
    if (!res.ok) return [];
    return (await res.json()).versions || [];
  }, []);

  const rollbackDetectionRule = useCallback(async (ruleId, versionNumber) => {
    const res = await fetch(`${API_BASE}/rules/${ruleId}/versions/${versionNumber}/rollback`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Không thể khôi phục phiên bản rule');
    const restored = await res.json();
    await fetchDetectionRules();
    addLog(`Đã khôi phục ${restored.name} từ phiên bản ${versionNumber}`);
    return restored;
  }, [addLog, fetchDetectionRules]);

  const fetchDetectionRuleConflicts = useCallback(async () => {
    const res = await fetch(`${API_BASE}/rules/conflicts`);
    if (!res.ok) return [];
    const conflicts = (await res.json()).conflicts || [];
    dispatch({ type: 'SET_DETECTION_RULE_CONFLICTS', payload: conflicts });
    return conflicts;
  }, []);

  const cloneDetectionRule = useCallback(async (ruleId) => {
    const res = await fetch(`${API_BASE}/rules/${ruleId}/clone`, { method: 'POST' });
    if (!res.ok) throw new Error('Không thể nhân bản rule');
    const clone = await res.json();
    await fetchDetectionRules();
    addLog(`Đã nhân bản rule: ${clone.name}`);
    return clone;
  }, [addLog, fetchDetectionRules]);

  const exportDetectionRules = useCallback(async () => {
    const res = await fetch(`${API_BASE}/rules/export`);
    if (!res.ok) throw new Error('Không thể xuất gói rule');
    return res.json();
  }, []);

  const importDetectionRules = useCallback(async (rules, strategy = 'skip') => {
    const res = await fetch(`${API_BASE}/rules/import`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rules, strategy }),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || 'Không thể import gói rule');
    }
    const result = await res.json();
    await fetchDetectionRules();
    addLog(`Import rule: ${result.imported.length} mới, ${result.skipped.length} bỏ qua`);
    return result;
  }, [addLog, fetchDetectionRules]);

  // ── Preview DOCX ────────────────────────────────────────

  const previewDocx = useCallback(async () => {
    previewRequestRef.current?.controller?.abort();
    const controller = new AbortController();
    const sequence = previewSequenceRef.current + 1;
    previewSequenceRef.current = sequence;
    const revision = documentRevisionRef.current;
    const clientRequestId = globalThis.crypto?.randomUUID?.() || `preview-${Date.now()}-${sequence}`;
    previewRequestRef.current = { controller, sequence, previewId: '' };
    dispatch({ type: 'SET_ERROR', payload: null });
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_SHOW_PREVIEW', payload: true });
    dispatch({
      type: 'SET_PREVIEW_STATE',
      payload: {
        status: 'generating', sequence, revision, progress: 0, phase: 'queued',
        previewId: '', jobId: '', errorCode: '', errorMessage: '',
      },
    });
    addLog('Queueing Preview job...');
    try {
      const incidentMetadata = state.reportSettings.reportType === 'incident_response'
        ? normalizeIncidentMetadata(state.reportSettings.incidentMetadata)
        : {};
      if (state.reportSettings.reportType === 'incident_response') {
        const incidentQuality = validateIncidentMetadata(incidentMetadata);
        if (!incidentQuality.valid) {
          throw new Error(`Thông tin Incident Response còn ${incidentQuality.errors.length} lỗi nghiêm trọng.`);
        }
        incidentMetadata.incidentQuality = incidentQuality.summary;
      }
      const body = {
        rows: state.rows,
        title: state.reportSettings.title,
        organization: state.reportSettings.organization,
        assessmentDate: state.reportSettings.assessmentDate,
        templatePath: state.reportSettings.templatePath,
        reportType: state.reportSettings.reportType,
        disablePlugins: state.reportSettings.disablePlugins,
        clientRequestId,
        metadata: {
          ...incidentMetadata,
          ruleSettings: state.reportSettings.ruleSettings,
        },
      };
      let res = await fetch(`${API_BASE}/preview-jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      // Compatibility fallback keeps older/flag-disabled backends usable.
      if (res.status === 404) {
        res = await fetch(`${API_BASE}/preview-docx`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: controller.signal,
        });
        if (!res.ok) throw new Error(`Preview error: ${res.status}`);
        const blob = await res.blob();
        dispatch({
          type: 'PREVIEW_READY',
          payload: {
            sequence, revision, blob,
            signature: res.headers?.get?.('X-Request-Signature') || JSON.stringify(body),
            data: { cacheMode: 'compatibility', expiresAt: '', previewId: '' },
          },
        });
        addLog('Preview generated through compatibility endpoint');
        return;
      }
      if (!res.ok) throw new Error(`Preview error: ${res.status}`);

      const created = await res.json();
      const previewId = created.previewId;
      if (!previewId) throw new Error('Preview Job response is missing previewId');
      if (previewRequestRef.current?.sequence !== sequence) return;
      previewRequestRef.current.previewId = previewId;
      dispatch({
        type: 'UPDATE_PREVIEW_JOB',
        payload: { sequence, data: {
          previewId, jobId: created.jobId || '', status: created.status || 'generating',
          progress: created.progress || 0, phase: created.phase || 'queued',
          signature: created.signature || '', templateHash: created.templateHash || '',
          expiresAt: created.expiresAt || '', cacheMode: created.cacheMode || 'pending',
        } },
      });

      let statePayload = created;
      while (previewRequestRef.current?.sequence === sequence) {
        if (['ready', 'failed', 'expired', 'stale', 'cancelled'].includes(statePayload.status)) break;
        await new Promise((resolve) => window.setTimeout(resolve, 500));
        if (previewRequestRef.current?.sequence !== sequence) return;
        const statusResponse = await fetch(`${API_BASE}/preview-jobs/${previewId}`, {
          signal: controller.signal,
        });
        if (!statusResponse.ok) throw new Error(`Preview status error: ${statusResponse.status}`);
        statePayload = await statusResponse.json();
        dispatch({
          type: 'UPDATE_PREVIEW_JOB',
          payload: { sequence, data: {
            status: statePayload.status === 'ready' ? 'current' : statePayload.status,
            progress: statePayload.progress || 0,
            phase: statePayload.phase || '',
            expiresAt: statePayload.expiresAt || '',
            cacheMode: statePayload.cacheMode || '',
            errorCode: statePayload.errorCode || '',
            errorMessage: statePayload.errorMessage || '',
          } },
        });
      }
      if (previewRequestRef.current?.sequence !== sequence) return;
      if (statePayload.status !== 'ready') {
        const terminalStatus = statePayload.status === 'expired' ? 'expired'
          : statePayload.status === 'stale' ? 'stale' : 'failed';
        dispatch({
          type: 'UPDATE_PREVIEW_JOB',
          payload: { sequence, data: {
            status: terminalStatus,
            errorCode: statePayload.errorCode || statePayload.status?.toUpperCase() || 'PREVIEW_FAILED',
            errorMessage: statePayload.errorMessage || 'Preview không sẵn sàng.',
          } },
        });
        throw new Error(statePayload.errorMessage || 'Preview job failed');
      }

      const content = await fetch(`${API_BASE}/preview-jobs/${previewId}/content`, {
        signal: controller.signal,
      });
      if (!content.ok) throw new Error(`Preview content error: ${content.status}`);
      const blob = await content.blob();
      if (previewRequestRef.current?.sequence !== sequence) return;
      dispatch({
        type: 'PREVIEW_READY',
        payload: {
          sequence, revision, blob,
          signature: statePayload.signature || created.signature || '',
          data: {
            previewId, jobId: created.jobId || statePayload.jobId || '',
            templateHash: statePayload.templateHash || created.templateHash || '',
            expiresAt: statePayload.expiresAt || '', cacheMode: statePayload.cacheMode || '',
          },
        },
      });
      addLog(revision === documentRevisionRef.current
        ? 'Preview is current and ready to reuse'
        : 'Preview completed but is stale because the document changed');
    } catch (err) {
      if (err.name === 'AbortError') return;
      dispatch({
        type: 'UPDATE_PREVIEW_JOB',
        payload: { sequence, data: { status: 'failed', errorMessage: err.message } },
      });
      dispatch({ type: 'SET_ERROR', payload: err.message });
      addLog(`Error: ${err.message}`);
    } finally {
      if (previewRequestRef.current?.sequence === sequence) {
        dispatch({ type: 'SET_LOADING', payload: false });
      }
    }
  }, [state.rows, state.reportSettings, addLog]);

  const closePreview = useCallback(() => {
    dispatch({ type: 'SET_SHOW_PREVIEW', payload: false });
  }, []);

  const cancelPreview = useCallback(async () => {
    const active = previewRequestRef.current;
    const previewId = active?.previewId || state.previewState.previewId;
    if (!previewId) return false;
    active?.controller?.abort();
    const res = await fetch(`${API_BASE}/preview-jobs/${previewId}`, { method: 'DELETE' });
    if (!res.ok) return false;
    previewRequestRef.current = null;
    dispatch({
      type: 'SET_PREVIEW_STATE',
      payload: {
        ...state.previewState, status: 'failed', errorCode: 'CANCELLED',
        errorMessage: 'Preview đã được hủy theo yêu cầu.',
      },
    });
    addLog('Preview job cancelled');
    return true;
  }, [state.previewState, addLog]);

  const savePreviewAsTemplate = useCallback(async (name, description = '') => {
    if (!state.previewBlob) {
      addLog('Không có bản preview để lưu làm template.');
      return false;
    }
    const dataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error || new Error('Không đọc được preview blob'));
      reader.readAsDataURL(state.previewBlob);
    });
    const filename = `${name.trim().replace(/[^a-zA-Z0-9_-]+/g, '-') || 'preview-template'}.docx`;
    const result = await uploadTemplate(
      filename, dataUrl, name, description, state.reportSettings.reportType,
    );
    return Boolean(result);
  }, [state.previewBlob, state.reportSettings.reportType, uploadTemplate, addLog]);

  // ── Save report as template ─────────────────────────────

  const saveReportAsTemplate = useCallback(async (name, description = '') => {
    if (!state.lastReportId) {
      addLog('No report to save as template');
      return false;
    }
    try {
      const res = await fetch(`${API_BASE}/reports/${state.lastReportId}/save-as-template`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          description,
          reportType: state.reportSettings.reportType || 'full',
        }),
      });
      if (res.ok) {
        const data = await res.json();
        addLog(`Saved as template: ${data.name}`);
        await fetchTemplates();
        return true;
      }
    } catch (err) {
      addLog(`Error: ${err.message}`);
    }
    return false;
  }, [state.lastReportId, state.reportSettings.reportType, addLog, fetchTemplates]);

  // ── Fetch report history ─────────────────────────────────

  const fetchReportHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/reports/history`);
      if (res.ok) {
        const data = await res.json();
        dispatch({ type: 'SET_REPORT_HISTORY', payload: data.reports || [] });
        return { ok: true, data };
      }
      return { ok: false, status: res.status };
    } catch (err) {
      console.warn('Could not load report history:', err);
      return { ok: false, error: err.message };
    }
  }, []);

  const fetchDashboardSummary = useCallback(async (days = 90) => {
    try {
      const res = await fetch(`${API_BASE}/dashboard/summary?days=${days}`);
      if (res.ok) {
        const data = await res.json();
        dispatch({ type: 'SET_DASHBOARD_SUMMARY', payload: data });
        return { ok: true, data };
      }
      return { ok: false, status: res.status };
    } catch (err) {
      console.warn('Could not load dashboard summary:', err);
      return { ok: false, error: err.message };
    }
  }, []);

  // ── Local workspace backup ────────────────────────────────

  const downloadWorkspaceBackup = useCallback(async () => {
    addLog('Đang tạo snapshot dữ liệu và template...');
    const res = await fetch(`${API_BASE}/system/backup`);
    if (!res.ok) {
      const error = await res.json().catch(() => ({}));
      throw new Error(error.detail || 'Không thể tạo bản sao lưu');
    }

    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename\*?=(?:UTF-8''|["']?)([^"';]+)/i);
    const filename = match?.[1] ? decodeURIComponent(match[1]) : 'reporter-pro-backup.zip';
    const url = URL.createObjectURL(blob);
    try {
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    } finally {
      URL.revokeObjectURL(url);
    }

    addLog(`Đã tải backup: ${filename}`);
    return { filename, size: blob.size };
  }, [addLog]);

  const previewWorkspaceRestore = useCallback(async (file) => {
    addLog(`Đang kiểm tra backup trước khi restore: ${file.name}`);
    const form = new FormData();
    form.append('backup', file, file.name);
    const res = await fetch(`${API_BASE}/system/restore/preview`, {
      method: 'POST',
      body: form,
    });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(payload.detail || 'Backup không hợp lệ');
    }
    addLog(`Dry-run hợp lệ: ${payload.templateCount} template`);
    return payload;
  }, [addLog]);

  const restoreWorkspaceBackup = useCallback(async (file, confirmationToken) => {
    addLog(`Đang restore workspace từ ${file.name}...`);
    const form = new FormData();
    form.append('backup', file, file.name);
    form.append('confirmationToken', confirmationToken);
    const res = await fetch(`${API_BASE}/system/restore`, {
      method: 'POST',
      body: form,
    });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(payload.detail || 'Không thể restore workspace');
    }
    addLog(`Đã restore workspace: ${payload.templateCount} template`);
    return payload;
  }, [addLog]);

  // ── Clear imported file ─────────────────────────────────

  const clearImportedFile = useCallback(() => {
    importRequestRef.current.controller?.abort();
    importRequestRef.current = { id: importRequestRef.current.id + 1, controller: null };
    dispatch({ type: 'SET_IMPORTED_FILE', payload: null });
    dispatch({ type: 'SET_IMPORTED_FILE_DATA', payload: null });
    dispatch({ type: 'SET_COLUMN_PREVIEW', payload: null });
    dispatch({ type: 'SET_COLUMN_MAPPING', payload: null });
    dispatch({ type: 'SET_ROWS', payload: [] });
    dispatch({ type: 'SET_PAYLOAD', payload: null });
    dispatch({ type: 'SET_PREVIEW_TEXT', payload: '' });
    dispatch({ type: 'SET_ERROR', payload: null });
    dispatch({ type: 'SET_LOADING', payload: false });
    addLog('Đã xóa file import. Bạn có thể chọn file mới.');
  }, [addLog]);

  const value = {
    ...state,
    setStep,
    setReportSettings,
    setColumnMapping,
    addRow,
    removeRow,
    updateRow,
    startRuleFromRow,
    clearRuleDraftSource,
    importFile,
    applyColumnMapping,
    normalizeRaw,
    loadSample,
    generateReport,
    validateRows,
    cancelReportJob,
    fetchReportJobs,
    downloadReportJob,
    fetchTemplates,
    addLog,
    // New: presets
    fetchPresets,
    savePreset,
    loadPreset,
    deletePreset,
    // New: template management
    uploadTemplate,
    updateTemplate,
    deleteTemplate,
    analyzeTemplate,
    fetchTemplateVersions,
    uploadTemplateVersion,
    rollbackTemplateVersion,
    fetchDetectionRules,
    saveDetectionRule,
    evaluateDetectionRule,
    reanalyzeRows,
    fetchDetectionRuleVersions,
    rollbackDetectionRule,
    fetchDetectionRuleConflicts,
    cloneDetectionRule,
    exportDetectionRules,
    importDetectionRules,
    // New: preview
    previewDocx,
    closePreview,
    cancelPreview,
    savePreviewAsTemplate,
    // New: save report as template
    saveReportAsTemplate,
    // New: report history
    fetchReportHistory,
    fetchDashboardSummary,
    // Local-first workspace protection
    downloadWorkspaceBackup,
    previewWorkspaceRestore,
    restoreWorkspaceBackup,
    // New: clear import
    clearImportedFile,
  };

  return (
    <ReporterContext.Provider value={value}>
      {children}
    </ReporterContext.Provider>
  );
}

export function useReporter() {
  const ctx = useContext(ReporterContext);
  if (!ctx) throw new Error('useReporter must be used within ReporterProvider');
  return ctx;
}

// Alias for components that import useReporterContext
export const useReporterContext = useReporter;

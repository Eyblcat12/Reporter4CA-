import { useRef, useState } from 'react';
import { AlertTriangle, Check, FileText, LoaderCircle, Upload } from 'lucide-react';
import { readTemplateSource } from './templateSource';
import TemplateSourceLibrary from './TemplateSourceLibrary';

const REPORT_TYPES = [
  ['full', 'Full'],
  ['server_only', 'Server'],
  ['client_only', 'Client'],
  ['summary', 'Summary'],
  ['technical', 'Technical'],
  ['incident_response', 'Incident Response'],
];

function metric(value) {
  return Number.isFinite(Number(value)) ? Number(value) : 0;
}

export default function NewTemplateWorkspace({ onCancel, onAnalyze, onCreate }) {
  const [source, setSource] = useState(null);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [readProgress, setReadProgress] = useState(0);
  const [reportType, setReportType] = useState('full');
  const [profileId, setProfileId] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [version, setVersion] = useState('0.1.0');
  const [analysis, setAnalysis] = useState(null);
  const [state, setState] = useState('idle');
  const [error, setError] = useState(null);
  const fileRef = useRef(null);

  const profileIdValid = /^[a-z0-9][a-z0-9._-]{1,127}$/.test(profileId);
  const canAnalyze =
    Boolean(source) && !libraryOpen && state !== 'reading' && state !== 'analyzing';
  const canCreate =
    Boolean(analysis) &&
    !libraryOpen &&
    profileIdValid &&
    Boolean(displayName.trim()) &&
    Boolean(version.trim()) &&
    state !== 'creating';

  async function chooseFile(event) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setState('reading');
    setError(null);
    setAnalysis(null);
    setReadProgress(0);
    try {
      const loaded = await readTemplateSource(file, setReadProgress);
      setSource({ ...loaded, size: file.size });
      if (!displayName.trim()) setDisplayName(file.name.replace(/\.docx$/i, ''));
      if (!profileId.trim()) {
        setProfileId(
          file.name
            .replace(/\.docx$/i, '')
            .toLocaleLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .replace(/[^a-z0-9._-]+/g, '-')
            .replace(/^-+|-+$/g, '')
            .slice(0, 128),
        );
      }
      setState('ready');
    } catch (readError) {
      setSource(null);
      setState('idle');
      setError(readError);
    }
  }

  function changeReportType(value) {
    setReportType(value);
    setAnalysis(null);
    setError(null);
    if (state === 'analyzed') setState('ready');
  }

  async function analyze() {
    if (!canAnalyze) return;
    setState('analyzing');
    setError(null);
    setAnalysis(null);
    try {
      const result = await onAnalyze({
        filename: source.filename,
        contentBase64: source.contentBase64,
        reportType,
      });
      setAnalysis(result);
      setState('analyzed');
    } catch (analysisError) {
      setState('ready');
      setError(analysisError);
    }
  }

  async function create(event) {
    event.preventDefault();
    if (!canCreate) return;
    setState('creating');
    setError(null);
    try {
      await onCreate({
        filename: source.filename,
        contentBase64: source.contentBase64,
        reportType,
        profileId: profileId.trim(),
        displayName: displayName.trim(),
        version: version.trim(),
      });
    } catch (createError) {
      setState('analyzed');
      setError(createError);
    }
  }

  const facts = analysis?.facts || {};
  const checklist = analysis?.mapping?.checklist || [];
  const anchorCount =
    metric(facts.contentControls?.length) +
    metric(facts.bookmarks?.length) +
    metric(facts.tokens?.length);
  const suggestedCount = checklist.filter((item) => item.suggestedAnchors?.length).length;

  return (
    <div className="ts-new-template">
      <header className="ts-new-template-head">
        <div>
          <span>Template source</span>
          <h2>Tạo workspace mới</h2>
        </div>
        <div className="ts-new-template-steps" aria-label="Tiến độ tạo workspace">
          <span className={source ? 'done' : 'current'}>1 · Chọn tệp</span>
          <span className={analysis ? 'done' : source ? 'current' : ''}>2 · Phân tích</span>
          <span className={analysis ? 'current' : ''}>3 · Tạo draft</span>
        </div>
      </header>

      {error && (
        <div className="ts-new-template-error" role="alert">
          <AlertTriangle size={16} />
          <div>
            <strong>Chưa thể tiếp tục</strong>
            <span>{error.message}</span>
          </div>
        </div>
      )}

      <div className="ts-new-template-grid">
        <form className="ts-new-template-form" onSubmit={create}>
          <div className="ts-new-template-section">
            <strong>Nguồn Word</strong>
            <input ref={fileRef} type="file" accept=".docx" hidden onChange={chooseFile} />
            <button
              className="ts-template-dropzone"
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={
                libraryOpen || state === 'reading' || state === 'analyzing' || state === 'creating'
              }
            >
              {state === 'reading' ? (
                <LoaderCircle className="spin" size={20} />
              ) : source ? (
                <FileText size={20} />
              ) : (
                <Upload size={20} />
              )}
              <span>
                <b>{source?.filename || 'Chọn template .docx'}</b>
                <small>
                  {state === 'reading'
                    ? `Đang đọc ${readProgress}%`
                    : source
                      ? `${(source.size / 1024 / 1024).toFixed(2)} MiB · nhấn để thay tệp`
                      : 'Tối đa 20 MiB'}
                </small>
              </span>
            </button>
            <button
              type="button"
              className="ts-button ts-button--secondary"
              disabled={state === 'reading' || state === 'analyzing' || state === 'creating'}
              onClick={() => setLibraryOpen((value) => !value)}
              aria-expanded={libraryOpen}
            >
              Thư viện nguồn
            </button>
            {libraryOpen && (
              <TemplateSourceLibrary
                onCancel={() => setLibraryOpen(false)}
                onSelect={(loaded) => {
                  setSource(loaded);
                  setAnalysis(null);
                  setError(null);
                  setState('ready');
                  setLibraryOpen(false);
                  if (!displayName.trim()) setDisplayName(loaded.filename.replace(/\.docx$/i, ''));
                }}
              />
            )}
            <label>
              Report type
              <select
                value={reportType}
                disabled={state === 'analyzing' || state === 'creating'}
                onChange={(event) => changeReportType(event.target.value)}
              >
                {REPORT_TYPES.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="ts-button ts-button--secondary"
              type="button"
              onClick={analyze}
              disabled={!canAnalyze || state === 'creating'}
            >
              {state === 'analyzing' && <LoaderCircle className="spin" size={15} />}
              {state === 'analyzing' ? 'Đang phân tích…' : analysis ? 'Phân tích lại' : 'Phân tích'}
            </button>
          </div>

          <div className="ts-new-template-section">
            <strong>Nhận diện workspace</strong>
            <label>
              Tên hiển thị
              <input
                value={displayName}
                maxLength="200"
                required
                onChange={(event) => setDisplayName(event.target.value)}
              />
            </label>
            <div className="ts-new-template-fields">
              <label>
                Profile ID
                <input
                  value={profileId}
                  pattern="[a-z0-9][a-z0-9._-]{1,127}"
                  required
                  aria-describedby="ts-profile-id-hint"
                  onChange={(event) => setProfileId(event.target.value)}
                />
                <small id="ts-profile-id-hint">
                  Chữ thường, số, dấu chấm, gạch ngang hoặc gạch dưới.
                </small>
              </label>
              <label>
                Version
                <input
                  value={version}
                  maxLength="64"
                  required
                  onChange={(event) => setVersion(event.target.value)}
                />
              </label>
            </div>
          </div>

          <footer>
            <button className="ts-button ts-button--secondary" type="button" onClick={onCancel}>
              Hủy
            </button>
            <button className="ts-button ts-button--primary" type="submit" disabled={!canCreate}>
              {state === 'creating' ? 'Đang tạo…' : 'Tạo workspace'}
            </button>
          </footer>
        </form>

        <section className="ts-template-analysis" aria-live="polite">
          {analysis ? (
            <>
              <div className="ts-template-analysis-state">
                <Check size={17} />
                <div>
                  <strong>Đã phân tích an toàn</strong>
                  <span>Chưa có mapping nào được phê duyệt.</span>
                </div>
              </div>
              <dl>
                <div>
                  <dt>Anchor</dt>
                  <dd>{anchorCount}</dd>
                </div>
                <div>
                  <dt>Heading</dt>
                  <dd>{metric(facts.headings?.length)}</dd>
                </div>
                <div>
                  <dt>Table</dt>
                  <dd>{metric(facts.tables?.length)}</dd>
                </div>
                <div>
                  <dt>Conflict</dt>
                  <dd>{metric(facts.anchorConflicts?.length)}</dd>
                </div>
              </dl>
              <div className="ts-template-coverage">
                <div>
                  <span>Mapping coverage</span>
                  <strong>0%</strong>
                </div>
                <i aria-hidden="true" />
                <small>
                  {suggestedCount}/{metric(analysis.mapping?.requiredCount)} semantic có gợi ý
                  anchor; mọi mapping vẫn cần người dùng duyệt.
                </small>
              </div>
              <code title={analysis.templateSha256}>{analysis.templateSha256}</code>
            </>
          ) : (
            <div className="ts-template-analysis-empty">
              <FileText size={24} />
              <strong>Chưa có kết quả phân tích</strong>
              <span>Chọn DOCX và chạy phân tích để xem cấu trúc trước khi tạo draft.</span>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

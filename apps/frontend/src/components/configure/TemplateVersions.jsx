import { useCallback, useEffect, useRef, useState } from 'react';
import { History, RotateCcw, Upload } from 'lucide-react';
import { useReporterContext } from '../../hooks/useReporter';

export default function TemplateVersions({ template }) {
  const { fetchTemplateVersions, uploadTemplateVersion, rollbackTemplateVersion } =
    useReporterContext();
  const [versions, setVersions] = useState([]);
  const inputRef = useRef(null);

  const refresh = useCallback(async () => {
    setVersions(await fetchTemplateVersions(template.id));
  }, [fetchTemplateVersions, template.id]);
  useEffect(() => {
    refresh();
  }, [refresh]);

  const upload = (file) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      await uploadTemplateVersion(template.id, reader.result, 'Uploaded from UI');
      await refresh();
    };
    reader.readAsDataURL(file);
  };

  return (
    <div className="tpl-version">
      <div className="tpl-version__head">
        <span>
          <History size={13} /> Lịch sử phiên bản
        </span>
        <button type="button" onClick={() => inputRef.current?.click()}>
          <Upload size={12} /> Phiên bản mới
        </button>
      </div>
      <input
        ref={inputRef}
        hidden
        type="file"
        accept=".docx"
        onChange={(event) => upload(event.target.files[0])}
      />
      {versions.map((version, index) => (
        <div className="tpl-version__row" key={version.id}>
          <span>
            <b>v{version.version}</b> {version.note || 'Không có ghi chú'}
            <small>{version.analysis?.compatibility?.status || 'unknown'}</small>
          </span>
          {index > 0 && version.analysis?.compatibility?.status !== 'incompatible' && (
            <button
              type="button"
              onClick={async () => {
                await rollbackTemplateVersion(template.id, version.version);
                await refresh();
              }}
            >
              <RotateCcw size={11} /> Khôi phục
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

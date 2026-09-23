import { useEffect, useState } from 'react';

export default function EditorDraftRecovery({
  api,
  workspaceId,
  sourceHash,
  semantic,
  busy,
  onRestore,
}) {
  const [page, setPage] = useState({ items: [], nextOffset: null });
  const [offset, setOffset] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState('');
  useEffect(() => {
    let current = true;
    setStatus('loading');
    api
      .list(workspaceId, offset)
      .then((result) => {
        if (current) {
          setPage(result);
          setStatus('ready');
        }
      })
      .catch((e) => {
        if (current) {
          setError(e.message);
          setStatus('error');
        }
      });
    return () => {
      current = false;
    };
  }, [api, workspaceId, offset, attempt]);
  return (
    <details className="ts-details">
      <summary>Bản nháp đã lưu</summary>
      {status === 'loading' && <p role="status">Đang đọc bản nháp…</p>}
      {status === 'error' && (
        <div role="alert">
          <p>{error}</p>
          <button type="button" onClick={() => setAttempt((a) => a + 1)}>
            Tải lại bản nháp
          </button>
        </div>
      )}
      {status === 'ready' && (
        <>
          {!page.items.some((item) => item.semantic === semantic) && (
            <p>Không có bản nháp của mục này trên trang hiện tại.</p>
          )}
          {page.items
            .filter((item) => item.semantic === semantic)
            .map((item) => (
              <div key={item.draftId}>
                <p>
                  Revision {item.baseRevision} · {item.updatedAt}
                  {item.stale ? ' · Đã có thay đổi mới' : ''}
                </p>
                <button
                  type="button"
                  disabled={busy || item.templateSha256 !== sourceHash}
                  onClick={() => onRestore(item)}
                >
                  Khôi phục bản nháp
                </button>
                {item.templateSha256 !== sourceHash && (
                  <small>Nguồn Word đã đổi; không thể áp dụng bản nháp này.</small>
                )}
              </div>
            ))}
          <button
            type="button"
            disabled={!offset}
            onClick={() => setOffset(Math.max(0, offset - 20))}
          >
            Trang trước
          </button>
          <button
            type="button"
            disabled={page.nextOffset === null}
            onClick={() => setOffset(page.nextOffset)}
          >
            Trang sau
          </button>
          <button type="button" onClick={() => setAttempt((a) => a + 1)}>
            Tải lại bản nháp
          </button>
        </>
      )}
    </details>
  );
}

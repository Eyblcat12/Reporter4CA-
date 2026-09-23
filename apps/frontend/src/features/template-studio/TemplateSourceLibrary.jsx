import { useEffect, useState } from 'react';
import { getTemplateLibraryEntry, listTemplateLibrary } from './templateStudioApi';

export default function TemplateSourceLibrary({ onSelect, onCancel }) {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('');
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selecting, setSelecting] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    listTemplateLibrary({ q: filter, offset, signal: controller.signal })
      .then((result) => {
        if (!controller.signal.aborted) setPage(result);
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(failure);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [filter, offset, attempt]);

  async function select(digest) {
    setSelecting(true);
    setError(null);
    try {
      const entry = await getTemplateLibraryEntry(digest);
      onSelect({
        filename: entry.filename,
        contentBase64: entry.contentBase64,
        size: Math.floor((entry.contentBase64.length * 3) / 4),
      });
    } catch (failure) {
      setError(failure);
    } finally {
      setSelecting(false);
    }
  }

  return (
    <section
      className="ts-source-library"
      aria-label="Thư viện template nguồn"
      aria-busy={loading || selecting}
    >
      <div className="ts-source-library-toolbar">
        <input
          aria-label="Tìm template đã lưu"
          placeholder="Tìm tên template…"
          value={query}
          disabled={selecting}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              setFilter(query);
              setOffset(0);
              setAttempt((value) => value + 1);
            }
          }}
        />
        <button
          type="button"
          className="ts-button ts-button--secondary"
          disabled={selecting}
          onClick={() => {
            setFilter(query);
            setOffset(0);
            setAttempt((value) => value + 1);
          }}
        >
          Tìm
        </button>
      </div>
      {error && (
        <div role="alert">
          {error.message}
          <button
            type="button"
            className="ts-button ts-button--secondary"
            disabled={selecting}
            onClick={() => setAttempt((value) => value + 1)}
          >
            Thử lại
          </button>
        </div>
      )}
      {loading ? (
        <p role="status">Đang tải thư viện…</p>
      ) : (
        !error && (
          <>
            <p role="status">{page?.total || 0} template đã lưu</p>
            {page?.backfillSkipped > 0 && (
              <p role="alert">
                {page.backfillSkipped} workspace cũ chưa thể bổ sung vào kho. Kiểm tra nguồn DOCX.
              </p>
            )}
            {!page?.items?.length && (
              <p>
                {filter
                  ? 'Không tìm thấy template phù hợp.'
                  : 'Chưa có template. Chọn DOCX từ máy và phân tích để lưu vào đây.'}
              </p>
            )}
          </>
        )
      )}
      {!loading && (
        <div className="ts-source-library-list">
          {page?.items?.map((item) => (
            <button
              type="button"
              key={item.sha256}
              className="ts-source-library-item"
              disabled={selecting}
              onClick={() => select(item.sha256)}
            >
              <strong>{item.filename}</strong>
              <small>
                {(item.size_bytes / 1048576).toFixed(2)} MiB · {item.reportTypes.join(', ')} ·{' '}
                {new Date(item.updated_at).toLocaleDateString('vi-VN')}
              </small>
              <code>{item.sha256.slice(0, 12)}</code>
            </button>
          ))}
        </div>
      )}
      {selecting && <p role="status">Đang lấy template…</p>}
      <div className="ts-source-library-toolbar">
        <button
          type="button"
          className="ts-button ts-button--secondary"
          disabled={loading || selecting || offset === 0}
          onClick={() => setOffset((value) => Math.max(0, value - 20))}
        >
          Trang trước
        </button>
        <button
          type="button"
          className="ts-button ts-button--secondary"
          disabled={loading || selecting || !page?.hasMore}
          onClick={() => setOffset((value) => value + 20)}
        >
          Trang sau
        </button>
        <button
          type="button"
          className="ts-button ts-button--secondary"
          disabled={selecting}
          onClick={onCancel}
        >
          Đóng thư viện
        </button>
      </div>
    </section>
  );
}

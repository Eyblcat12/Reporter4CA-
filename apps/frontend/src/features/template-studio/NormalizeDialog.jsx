import { useEffect, useRef, useState } from 'react';
import { getTemplateStructure, normalizeTemplateWorkspace } from './templateStudioApi';
import { semanticDefinition } from './semanticCatalog';

export default function NormalizeDialog({ workspace, onDismiss, onCreated }) {
  const [structure, setStructure] = useState(null);
  const [placements, setPlacements] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const dialog = useRef(null);
  const semantics = workspace.analysis.mapping.checklist.map((item) => item.semantic);
  useEffect(() => {
    let active = true;
    dialog.current?.focus();
    getTemplateStructure(workspace.workspaceId)
      .then((value) => {
        if (active) setStructure(value);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [workspace.workspaceId]);
  const ready =
    structure && semantics.every((semantic) => placements[semantic]?.blockIndex !== undefined);
  async function normalize() {
    setBusy(true);
    setError('');
    try {
      const created = await normalizeTemplateWorkspace(workspace.workspaceId, {
        expectedRevision: structure.revision,
        placements: semantics.map((semantic) => ({
          semantic,
          mode: 'after',
          ...placements[semantic],
        })),
      });
      await onCreated(created);
      onDismiss();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  function keys(event) {
    if (event.key === 'Escape' && !busy) onDismiss();
    if (event.key !== 'Tab') return;
    const nodes = [
      ...dialog.current.querySelectorAll('button:not(:disabled),select:not(:disabled)'),
    ];
    if (!nodes.length) return;
    if (event.shiftKey && document.activeElement === nodes[0]) {
      event.preventDefault();
      nodes.at(-1).focus();
    } else if (!event.shiftKey && document.activeElement === nodes.at(-1)) {
      event.preventDefault();
      nodes[0].focus();
    }
  }
  return (
    <div className="ts-manager-backdrop" role="presentation">
      <section
        className="ts-manager ts-normalize-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="normalize-title"
        ref={dialog}
        tabIndex={-1}
        onKeyDown={keys}
      >
        <header className="ts-manager-head">
          <div>
            <h1 id="normalize-title">Chuẩn hóa cấu trúc</h1>
            <p>
              Tạo bản sao có anchor. “Thay nội dung” đánh dấu vùng sẽ được thay khi xuất; tệp gốc
              giữ nguyên.
            </p>
          </div>
          <button className="ts-button ts-button--secondary" onClick={onDismiss} disabled={busy}>
            Đóng
          </button>
        </header>
        <div className="ts-normalize-body">
          {error && <p role="alert">{error}</p>}
          {!structure && !error && <p role="status">Đang đọc đoạn và bảng…</p>}
          {structure && (
            <table className="ts-mapping-table">
              <thead>
                <tr>
                  <th>Nội dung</th>
                  <th>Vị trí trong Word</th>
                  <th>Cách đặt</th>
                </tr>
              </thead>
              <tbody>
                {semantics.map((semantic) => (
                  <tr key={semantic}>
                    <td>{semanticDefinition(semantic).label}</td>
                    <td>
                      <select
                        aria-label={`Vị trí ${semantic}`}
                        value={placements[semantic]?.blockIndex ?? ''}
                        onChange={(e) =>
                          setPlacements((p) => ({
                            ...p,
                            [semantic]: {
                              ...p[semantic],
                              blockIndex:
                                e.target.value === '' ? undefined : Number(e.target.value),
                            },
                          }))
                        }
                        disabled={busy}
                      >
                        <option value="">Chọn đoạn / bảng</option>
                        {structure.blocks.map((block) => (
                          <option key={block.index} value={block.index}>
                            {block.index + 1} · {block.kind === 'table' ? 'Bảng' : 'Đoạn'} ·{' '}
                            {block.text}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <select
                        aria-label={`Chế độ ${semantic}`}
                        value={placements[semantic]?.mode || 'after'}
                        onChange={(e) =>
                          setPlacements((p) => ({
                            ...p,
                            [semantic]: { ...p[semantic], mode: e.target.value },
                          }))
                        }
                        disabled={busy}
                      >
                        <option value="after">Chèn phía sau</option>
                        <option value="replace">Thay nội dung</option>
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <footer className="ts-manager-head">
          <span>Mapping vẫn cần được duyệt sau chuẩn hóa.</span>
          <button
            className="ts-button ts-button--primary"
            disabled={!ready || busy}
            onClick={normalize}
          >
            {busy ? 'Đang chuẩn hóa…' : 'Tạo bản chuẩn hóa'}
          </button>
        </footer>
      </section>
    </div>
  );
}

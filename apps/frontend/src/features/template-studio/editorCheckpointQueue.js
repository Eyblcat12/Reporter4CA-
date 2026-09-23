// One serialized writer per editor/source/semantic. Failed requests retain their
// operation identity so a lost response can be retried without duplicate writes.
const newId = () => crypto.randomUUID().replaceAll('-', '');

export function createCheckpointQueue(api, changed = () => {}, id = newId) {
  const entries = new Map();
  const sessionId = id();
  function update(entry, status, error = null) {
    entry.status = status;
    entry.error = error;
    changed();
  }
  function edit(key, context, draft) {
    let entry = entries.get(key);
    if (!entry) {
      entry = { ...context, draftId: id(), sessionId, revision: 0, latest: null, saved: null };
      entries.set(key, entry);
    }
    if (entry.closing || entry.retirement)
      throw new Error('Đang đóng bản nháp, vui lòng thử lại thao tác đóng trước.');
    entry.latest = structuredClone(draft);
    clearTimeout(entry.timer);
    if (entry.status !== 'error') {
      update(entry, 'pending');
      entry.timer = setTimeout(() => {
        flush(key).catch(() => {});
      }, 600);
    } else changed();
  }
  async function flush(key) {
    const entry = entries.get(key);
    if (!entry) return;
    clearTimeout(entry.timer);
    if (entry.running) return entry.running;
    entry.running = (async () => {
      while (entry.request || JSON.stringify(entry.saved) !== JSON.stringify(entry.latest)) {
        entry.request ||= {
          sessionId: entry.sessionId,
          operationId: id(),
          expectedDraftRevision: entry.revision,
          baseRevision: entry.baseRevision,
          templateSha256: entry.templateSha256,
          semantic: entry.semantic,
          baseline: entry.baseline,
          draft: structuredClone(entry.latest),
        };
        update(entry, 'saving');
        try {
          const result = await api.save(entry.workspaceId, entry.draftId, entry.request);
          entry.revision = result.draftRevision;
          entry.saved = entry.request.draft;
          entry.request = null;
        } catch (error) {
          update(entry, 'error', error);
          throw error;
        }
      }
      update(entry, 'saved');
    })();
    try {
      await entry.running;
    } finally {
      entry.running = null;
    }
  }
  async function retire(key, reason) {
    const entry = entries.get(key);
    if (!entry) return;
    entry.closing = true;
    try {
      await flush(key);
      entry.retirement ||= { operationId: id(), expectedDraftRevision: entry.revision, reason };
      update(entry, 'closing');
      await api.retire(entry.workspaceId, entry.draftId, entry.retirement);
      entries.delete(key);
      changed();
    } catch (error) {
      update(entry, 'error', error);
      throw error;
    } finally {
      entry.closing = false;
    }
  }
  return {
    adopt(key, record) {
      if (entries.has(key)) throw new Error('Bỏ bản nháp đang chỉnh trước khi khôi phục bản khác.');
      entries.set(key, {
        ...record,
        revision: record.draftRevision,
        latest: structuredClone(record.draft),
        saved: structuredClone(record.draft),
        status: 'saved',
      });
      changed();
    },
    retry(key) {
      const entry = entries.get(key);
      return entry?.retirement ? retire(key, entry.retirement.reason) : flush(key);
    },
    edit,
    flush,
    retire,
    get: (key) => entries.get(key),
    hasPending: () => [...entries.values()].some((e) => e.status !== 'saved'),
    stop: () => {
      for (const entry of entries.values()) clearTimeout(entry.timer);
    },
  };
}

const MAX_FIXTURE_BYTES = 30 * 1024 * 1024;

export function readValidationFixture(file) {
  const csv = file?.name?.toLocaleLowerCase().endsWith('.csv');
  if (!csv && !file?.name?.toLocaleLowerCase().endsWith('.json')) {
    return Promise.reject(new Error('Fixture phải là tệp JSON hoặc Tracking CSV.'));
  }
  if (file.size > MAX_FIXTURE_BYTES) {
    return Promise.reject(new Error('Fixture vượt giới hạn 30 MiB.'));
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Không thể đọc fixture trên máy.'));
    reader.onload = async () => {
      try {
        if (csv) {
          const contentBase64 = String(reader.result);
          const previewResponse = await fetch('/api/column-preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: file.name, contentBase64 }),
          });
          const preview = await previewResponse.json();
          if (!previewResponse.ok) {
            throw new Error(
              typeof preview.detail === 'string'
                ? preview.detail
                : 'Không nhận diện được cột Tracking.',
            );
          }
          if (preview.sheetNames?.length > 1) {
            throw new Error('Fixture có nhiều sheet. Hãy dùng bản Tracking một sheet để kiểm thử.');
          }
          const response = await fetch('/api/import-file', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              filename: file.name,
              contentBase64,
              columnMapping: preview.suggestedMapping || {},
              headerRow: preview.headerRow ?? 0,
              sheetName: preview.sheetNames?.[0] || '',
              defaultType: 'server',
            }),
          });
          const imported = await response.json();
          if (!response.ok || !imported.rows?.length)
            throw new Error(
              typeof imported.detail === 'string'
                ? imported.detail
                : 'Không thể đọc dữ liệu Tracking CSV.',
            );
          resolve({ filename: file.name, rows: imported.rows, metadata: {} });
          return;
        }
        const parsed = JSON.parse(String(reader.result || ''));
        const rows = Array.isArray(parsed) ? parsed : parsed?.rows;
        if (!Array.isArray(rows) || !rows.length) {
          throw new Error('Fixture phải có mảng rows không rỗng.');
        }
        if (rows.some((row) => !row || Array.isArray(row) || typeof row !== 'object')) {
          throw new Error('Mỗi phần tử trong rows phải là một object.');
        }
        const metadata = Array.isArray(parsed) ? {} : parsed?.metadata || {};
        if (!metadata || Array.isArray(metadata) || typeof metadata !== 'object') {
          throw new Error('Metadata của fixture phải là một object.');
        }
        resolve({ filename: file.name, rows, metadata });
      } catch (error) {
        reject(error instanceof SyntaxError ? new Error('Fixture JSON không hợp lệ.') : error);
      }
    };
    if (csv) reader.readAsDataURL(file);
    else reader.readAsText(file, 'utf-8');
  });
}

export function downloadValidationArtifact({ blob, filename }) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

const MAX_FIXTURE_BYTES = 30 * 1024 * 1024;

export function readValidationFixture(file) {
  if (!file?.name?.toLocaleLowerCase().endsWith('.json')) {
    return Promise.reject(new Error('Fixture phải là tệp JSON.'));
  }
  if (file.size > MAX_FIXTURE_BYTES) {
    return Promise.reject(new Error('Fixture vượt giới hạn 30 MiB.'));
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Không thể đọc fixture trên máy.'));
    reader.onload = () => {
      try {
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
    reader.readAsText(file, 'utf-8');
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

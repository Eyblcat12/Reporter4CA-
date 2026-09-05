const MAX_DRAFT_BYTES = 30 * 1024 * 1024;

export function readDraftFile(file) {
  if (!file?.name?.toLocaleLowerCase().endsWith('.rptdraft')) {
    return Promise.reject(new Error('Chỉ chấp nhận tệp .rptdraft.'));
  }
  if (file.size > MAX_DRAFT_BYTES) {
    return Promise.reject(new Error('Draft vượt giới hạn 30 MiB.'));
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Không thể đọc draft trên máy.'));
    reader.onload = () => {
      const value = String(reader.result || '');
      const separator = value.indexOf(',');
      if (separator < 0) {
        reject(new Error('Draft không có dữ liệu base64 hợp lệ.'));
        return;
      }
      resolve({ filename: file.name, contentBase64: value.slice(separator + 1) });
    };
    reader.readAsDataURL(file);
  });
}

export function downloadDraft({ filename, contentBase64 }) {
  const binary = window.atob(contentBase64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  const url = URL.createObjectURL(new Blob([bytes], { type: 'application/zip' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export const MAX_TEMPLATE_BYTES = 20 * 1024 * 1024;

export function readTemplateSource(file, onProgress = () => {}) {
  if (!file?.name?.toLocaleLowerCase().endsWith('.docx')) {
    return Promise.reject(new Error('Chỉ chấp nhận template Word .docx.'));
  }
  if (!file.size) {
    return Promise.reject(new Error('Template đang trống.'));
  }
  if (file.size > MAX_TEMPLATE_BYTES) {
    return Promise.reject(new Error('Template vượt giới hạn an toàn 20 MiB.'));
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Không thể đọc template trên máy.'));
    reader.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    reader.onload = () => {
      const value = String(reader.result || '');
      const separator = value.indexOf(',');
      if (separator < 0 || !value.slice(separator + 1)) {
        reject(new Error('Template không có dữ liệu base64 hợp lệ.'));
        return;
      }
      onProgress(100);
      resolve({ filename: file.name, contentBase64: value.slice(separator + 1) });
    };
    reader.readAsDataURL(file);
  });
}

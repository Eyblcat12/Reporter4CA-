import { MAX_TEMPLATE_BYTES, readTemplateSource } from './templateSource';

describe('Template Studio DOCX source reader', () => {
  it('reads a bounded DOCX and reports completion', async () => {
    const progress = vi.fn();
    const file = new File(['word-package'], 'customer.docx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    });

    await expect(readTemplateSource(file, progress)).resolves.toEqual(
      expect.objectContaining({ filename: 'customer.docx' }),
    );
    expect(progress).toHaveBeenLastCalledWith(100);
  });

  it('rejects unrelated, empty, and oversized files before upload', async () => {
    await expect(
      readTemplateSource(new File(['x'], 'customer.pdf', { type: 'application/pdf' })),
    ).rejects.toThrow('Chỉ chấp nhận template Word .docx.');
    await expect(readTemplateSource(new File([], 'empty.docx'))).rejects.toThrow(
      'Template đang trống.',
    );
    await expect(
      readTemplateSource({ name: 'large.docx', size: MAX_TEMPLATE_BYTES + 1 }),
    ).rejects.toThrow('Template vượt giới hạn an toàn 20 MiB.');
  });
});

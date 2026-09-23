import { fireEvent, render, screen } from '@testing-library/react';
import TemplateStudioNext, { comparisonDocument } from './TemplateStudioNext';

it('isolates the new UI and exposes explicit comparison navigation', () => {
  const onCompare = vi.fn((event) => event.preventDefault());
  render(<TemplateStudioNext onCompare={onCompare} />);
  expect(screen.getByText(/không lưu vào tool/)).toBeVisible();
  const frame = screen.getByTitle('Mẫu Stitch — Mapping Workspace');
  expect(frame).toHaveAttribute('sandbox', '');
  expect(frame).not.toHaveAttribute('src');
  fireEvent.click(screen.getByText('Xem UI hiện tại'));
  expect(onCompare).toHaveBeenCalledTimes(1);
});

it('ships local styles without external scripts, handlers or fake autosave', () => {
  const doc = new DOMParser().parseFromString(comparisonDocument, 'text/html');
  expect(doc.querySelectorAll('script, link, iframe, [onclick], img')).toHaveLength(0);
  expect(doc.querySelectorAll('button:not([disabled])')).toHaveLength(0);
  expect(doc.body.textContent).not.toContain('Đã tự động lưu');
  expect(doc.head.textContent).toContain('.flex');
  expect(doc.querySelector('meta[http-equiv="Content-Security-Policy"]').content).toContain(
    "connect-src 'none'",
  );
});

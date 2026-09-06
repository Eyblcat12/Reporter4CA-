import { render, screen } from '@testing-library/react';
import Sidebar from './Sidebar';

vi.mock('../../hooks/useReporter', () => ({
  useReporterContext: () => ({
    currentStep: 1,
    setStep: vi.fn(),
    counts: { servers: 2, clients: 3, total: 5 },
  }),
}));

vi.mock('../../i18n', () => ({
  useI18n: () => ({
    t: (key) =>
      ({
        'step.import': 'Import dữ liệu',
        'step.configure': 'Cấu hình',
        'step.export': 'Xuất báo cáo',
        'templateStudio.title': 'Template Studio',
        'templateStudio.description': 'Chuẩn hóa template Word',
        'common.servers': 'Máy chủ',
        'common.clients': 'Máy trạm',
        'common.total': 'Tổng',
      })[key] || key,
  }),
}));

vi.mock('./ThemeToggle', () => ({ default: () => <button>Theme</button> }));
vi.mock('./LanguageSwitcher', () => ({ default: () => <button>Language</button> }));

describe('Sidebar Template Studio navigation', () => {
  it('exposes Template Studio as a separate tool without changing report steps', () => {
    render(<Sidebar collapsed={false} onToggle={vi.fn()} />);

    expect(screen.getByRole('link', { name: /Template Studio/ })).toHaveAttribute(
      'href',
      '?view=template-studio',
    );
    expect(screen.getByRole('button', { name: /Import dữ liệu/ })).toBeEnabled();
    expect(screen.getByRole('button', { name: /Cấu hình/ })).toBeEnabled();
    expect(screen.getByRole('button', { name: /Xuất báo cáo/ })).toBeEnabled();
  });
});

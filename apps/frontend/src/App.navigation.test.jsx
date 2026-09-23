import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import App from './App';

vi.mock('./components/layout/AppShell', () => ({
  default: function MockAppShell({ onOpenStudio }) {
    const [value, setValue] = useState('');
    return (
      <>
        <input aria-label="Report draft" value={value} onChange={(e) => setValue(e.target.value)} />
        <a href="?view=template-studio" onClick={onOpenStudio}>
          Open studio
        </a>
      </>
    );
  },
}));
vi.mock('./features/template-studio/TemplateStudioRoute.jsx', () => ({
  default: function MockStudio({ onReturn }) {
    const [value, setValue] = useState('');
    return (
      <>
        <input
          aria-label="Mapping draft"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <a href="./" onClick={onReturn}>
          Return to report
        </a>
      </>
    );
  },
}));
vi.mock('./components/shared/CommandPalette', () => ({ default: () => null }));
vi.mock('./components/shared/KeyboardShortcuts', () => ({ default: () => null }));
vi.mock('./components/shared/ReportJobPanel', () => ({ default: () => null }));
vi.mock('./features/template-studio-next/TemplateStudioNext.jsx', () => ({
  default: ({ onCompare, onReturn }) => (
    <>
      <p>New Studio comparison</p>
      <a href="?view=template-studio" onClick={onCompare}>
        Compare old Studio
      </a>
      <a href="./" onClick={onReturn}>
        Return from comparison
      </a>
    </>
  ),
}));

beforeEach(() => {
  vi.stubGlobal('localStorage', { getItem: () => null, setItem: vi.fn() });
  window.history.replaceState(null, '', '/');
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true, json: async () => ({ managedByLauncher: true }) }),
  );
});
afterEach(() => vi.unstubAllGlobals());

it('preserves both drafts and one launcher session through navigation and Back', async () => {
  const view = render(<App />);
  fireEvent.change(screen.getByLabelText('Report draft'), {
    target: { value: 'Tracking 30 hosts' },
  });
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith('/api/runtime/browser/open', expect.anything()),
  );
  fireEvent.click(screen.getByText('Open studio'));
  fireEvent.change(await screen.findByLabelText('Mapping draft'), {
    target: { value: 'Custom anchor' },
  });
  fireEvent.click(screen.getByText('Return to report'));
  expect(screen.getByLabelText('Report draft')).toHaveValue('Tracking 30 hosts');
  fireEvent.click(screen.getByText('Open studio'));
  expect(screen.getByLabelText('Mapping draft')).toHaveValue('Custom anchor');
  window.history.replaceState(null, '', '/');
  fireEvent.popState(window);
  expect(screen.getByLabelText('Report draft')).toBeVisible();
  const calls = fetch.mock.calls.map(([url]) => url);
  expect(calls.filter((url) => url === '/api/runtime/browser/open')).toHaveLength(1);
  expect(calls).not.toContain('/api/runtime/browser/close');
  view.unmount();
});

it('registers a launcher session when opening Studio directly', async () => {
  window.history.replaceState(null, '', '/?view=template-studio');
  render(<App />);
  expect(await screen.findByLabelText('Mapping draft')).toBeVisible();
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith('/api/runtime/browser/open', expect.anything()),
  );
});

it('keeps old Studio and report drafts when visiting the isolated comparison', async () => {
  render(<App />);
  fireEvent.change(screen.getByLabelText('Report draft'), { target: { value: 'Keep report' } });
  fireEvent.click(screen.getByText('Open studio'));
  fireEvent.change(await screen.findByLabelText('Mapping draft'), {
    target: { value: 'Keep mapping' },
  });
  fireEvent.click(screen.getByText('So sánh UI mới (dữ liệu mẫu)'));
  expect(await screen.findByText('New Studio comparison')).toBeVisible();
  expect(window.location.search).toBe('?view=template-studio-next');
  fireEvent.click(screen.getByText('Compare old Studio'));
  expect(screen.getByLabelText('Mapping draft')).toHaveValue('Keep mapping');
  fireEvent.click(screen.getByText('Return to report'));
  expect(screen.getByLabelText('Report draft')).toHaveValue('Keep report');
  expect(fetch.mock.calls.filter(([url]) => url === '/api/runtime/browser/open')).toHaveLength(1);
});

it('opens comparison directly without mounting the old Studio', async () => {
  window.history.replaceState(null, '', '/?view=template-studio-next');
  render(<App />);
  expect(await screen.findByText('New Studio comparison')).toBeVisible();
  expect(screen.queryByLabelText('Mapping draft')).not.toBeInTheDocument();
  window.history.replaceState(null, '', '/?view=template-studio');
  fireEvent.popState(window);
  expect(await screen.findByLabelText('Mapping draft')).toBeVisible();
});

import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import RuntimeLifecycle from './RuntimeLifecycle';

vi.mock('../../i18n', () => ({
  useI18n: () => ({ locale: 'vi' }),
}));

const okResponse = {
  ok: true,
  json: async () => ({ managedByLauncher: true }),
};

describe('RuntimeLifecycle', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okResponse));
    Object.defineProperty(navigator, 'sendBeacon', {
      configurable: true,
      value: vi.fn(() => true),
    });
    vi.spyOn(window, 'close').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('registers the tab and sends a close beacon on pagehide', async () => {
    render(<RuntimeLifecycle />);
    await act(async () => Promise.resolve());
    expect(fetch).toHaveBeenCalledWith(
      '/api/runtime/browser/open',
      expect.objectContaining({ method: 'POST' }),
    );

    fireEvent(window, new Event('pagehide'));

    expect(navigator.sendBeacon).toHaveBeenCalledWith(
      '/api/runtime/browser/close',
      expect.any(Blob),
    );
  });

  it('shows a stopped state and attempts to close after backend loss', async () => {
    fetch
      .mockResolvedValueOnce(okResponse)
      .mockRejectedValue(new Error('backend stopped'));
    render(<RuntimeLifecycle />);
    await act(async () => Promise.resolve());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(screen.getByRole('alert')).toHaveTextContent('Reporter Pro đã dừng');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(700);
    });
    expect(window.close).toHaveBeenCalled();
  });
});

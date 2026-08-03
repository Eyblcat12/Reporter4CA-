import { useEffect, useRef, useState } from 'react';
import { Power } from 'lucide-react';
import { useI18n } from '../../i18n';
import './RuntimeLifecycle.css';

const HEARTBEAT_MS = 2500;
const FAILURE_LIMIT = 2;

function newSessionId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `browser-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function postLifecycle(path, sessionId) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sessionId }),
    cache: 'no-store',
    keepalive: true,
  });
  if (!response.ok) throw new Error(`Lifecycle request failed (${response.status})`);
  return response.json();
}

export default function RuntimeLifecycle() {
  const { locale } = useI18n();
  const sessionIdRef = useRef(newSessionId());
  const [stopped, setStopped] = useState(false);

  useEffect(() => {
    const sessionId = sessionIdRef.current;
    let disposed = false;
    let connected = false;
    let failures = 0;

    const markStopped = () => {
      if (disposed || !connected) return;
      setStopped(true);
      window.setTimeout(() => {
        // Browsers only permit this for windows they consider script-opened.
        // The shutdown screen remains visible when that security rule blocks it.
        window.close();
      }, 700);
    };

    const heartbeat = async () => {
      try {
        const status = await postLifecycle('/api/runtime/browser/heartbeat', sessionId);
        if (disposed) return;
        connected = true;
        failures = 0;
        if (!status.managedByLauncher) return;
      } catch {
        failures += 1;
        if (failures >= FAILURE_LIMIT) markStopped();
      }
    };

    postLifecycle('/api/runtime/browser/open', sessionId)
      .then(() => {
        connected = true;
        failures = 0;
      })
      .catch(() => {});

    const interval = window.setInterval(heartbeat, HEARTBEAT_MS);
    const notifyClose = () => {
      const body = JSON.stringify({ sessionId });
      if (navigator.sendBeacon) {
        navigator.sendBeacon(
          '/api/runtime/browser/close',
          new Blob([body], { type: 'application/json' }),
        );
        return;
      }
      fetch('/api/runtime/browser/close', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        keepalive: true,
      }).catch(() => {});
    };

    window.addEventListener('pagehide', notifyClose);
    return () => {
      disposed = true;
      window.clearInterval(interval);
      window.removeEventListener('pagehide', notifyClose);
      notifyClose();
    };
  }, []);

  if (!stopped) return null;

  const isVietnamese = locale === 'vi';
  return (
    <div className="runtime-stopped" role="alert" aria-live="assertive">
      <div className="runtime-stopped__card">
        <span className="runtime-stopped__icon"><Power size={26} /></span>
        <h1>{isVietnamese ? 'Reporter Pro đã dừng' : 'Reporter Pro has stopped'}</h1>
        <p>
          {isVietnamese
            ? 'Launcher hoặc cửa sổ CMD đã đóng. Bạn có thể đóng tab này và chạy lại start.bat.'
            : 'The launcher or command window was closed. Close this tab and run start.bat again.'}
        </p>
      </div>
    </div>
  );
}

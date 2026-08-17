export default async function globalTeardown() {
  try {
    await fetch('http://127.0.0.1:4173/__e2e_shutdown', {
      method: 'POST',
      signal: AbortSignal.timeout(3000),
    });
  } catch {
    // The dedicated E2E server may already have stopped after a failed startup.
  }
}

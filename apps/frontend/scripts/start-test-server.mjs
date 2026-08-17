import react from '@vitejs/plugin-react';
import { createServer } from 'vite';

const shutdownPlugin = {
  name: 'reporter-e2e-shutdown',
  configureServer(devServer) {
    devServer.middlewares.use('/__e2e_shutdown', (request, response) => {
      if (request.method !== 'POST') {
        response.statusCode = 405;
        response.end();
        return;
      }
      response.statusCode = 204;
      response.end();
      setTimeout(async () => {
        await shutdown();
        process.exit(0);
      }, 10);
    });
  },
};

const server = await createServer({
  configFile: false,
  plugins: [react(), shutdownPlugin],
  server: { host: '127.0.0.1', port: 4173, strictPort: true },
});

await server.listen();
server.printUrls();

let closing = false;
async function shutdown() {
  if (closing) return;
  closing = true;
  await server.close();
}

for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
  process.once(signal, async () => {
    await shutdown();
    process.exit(0);
  });
}

process.stdin.once('end', shutdown);

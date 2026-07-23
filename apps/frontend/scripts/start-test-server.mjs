import react from '@vitejs/plugin-react';
import { createServer } from 'vite';

const server = await createServer({
  configFile: false,
  plugins: [react()],
  server: { host: '127.0.0.1', port: 4173, strictPort: true },
});

await server.listen();
server.printUrls();

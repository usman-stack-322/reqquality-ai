import { defineConfig } from 'vite';
import { readFileSync } from 'node:fs';

export default defineConfig(({ command, isPreview }) => ({
  server: {
    port: 5173,
    strictPort: true,
    // Local certificates are only needed by the development server.
    https: command === 'serve' && !isPreview ? {
      key: readFileSync(new URL('../backend/.certs/localhost-key.pem', import.meta.url)),
      cert: readFileSync(new URL('../backend/.certs/localhost.pem', import.meta.url)),
    } : undefined,
    proxy: {
      '/api': { target: 'https://127.0.0.1:5000', secure: false },
    },
  },
}));

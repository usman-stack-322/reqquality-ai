import { defineConfig } from 'vite';
import { readFileSync } from 'node:fs';

export default defineConfig({
  server: {
    port: 5173,
    strictPort: true,
    https: {
      key: readFileSync(new URL('../backend/.certs/localhost-key.pem', import.meta.url)),
      cert: readFileSync(new URL('../backend/.certs/localhost.pem', import.meta.url)),
    },
    proxy: {
      '/api': { target: 'https://127.0.0.1:5000', secure: false },
    },
  },
});

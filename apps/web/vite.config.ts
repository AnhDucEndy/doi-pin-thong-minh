import { defineConfig } from 'vite';
const target = process.env.DEV_API_TARGET ?? 'http://127.0.0.1:8000';
export default defineConfig({
  server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy: { '/v1': target, '/health': target } },
});

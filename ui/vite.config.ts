import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: '/ui/',
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/v1': {
        target: process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8086',
        changeOrigin: true,
      },
      '/api': {
        target: process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8086',
        changeOrigin: true,
      },
      '/healthz': {
        target: process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8086',
        changeOrigin: true,
      },
    },
  },
});

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backend = 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  base: '/',
  define: {
    __BUILD__: JSON.stringify(process.env.VITE_BUILD ?? 'dev'),
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: backend, changeOrigin: false },
      '/health': { target: backend, changeOrigin: false },
      '/version': { target: backend, changeOrigin: false },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});

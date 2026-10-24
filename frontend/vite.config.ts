/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import {configDefaults} from 'vitest/config'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'

// Django serves the API and the previous interface on :8010 during development.
// changeOrigin stays false on purpose: Django's CSRF check compares Origin with Host, and both must stay
// localhost:5173 for the session cookie and X-CSRFToken to work through the proxy.
const django = process.env.DJANGO_URL ?? 'http://127.0.0.1:8010'

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: django },
      '/legacy': { target: django },
      '/static': { target: django },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1500,
  },
  test: {
    exclude: [...configDefaults.exclude, 'tests/**'], // Playwright runs separately.
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})

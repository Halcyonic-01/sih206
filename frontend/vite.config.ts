import {defineConfig} from 'vite';

export default defineConfig({
  base: '/static/records/',
  build: {outDir: 'dist/records', emptyOutDir: true},
  server: {proxy: {'/api': 'http://127.0.0.1:8010', '/accounts': 'http://127.0.0.1:8010'}}
});

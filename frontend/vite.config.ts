/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: { host: '127.0.0.1', port: 5173, proxy: {
    '/api': 'http://127.0.0.1:8000',
    '/play': 'http://127.0.0.1:8000',  // playtest 部署（StaticFiles）在后端 8000
  } },
  test: { environment: 'jsdom', globals: true, setupFiles: ['./src/setup.ts'] },
})

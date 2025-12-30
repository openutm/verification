/// <reference types="vitest" />
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8989',
      '/health': 'http://localhost:8989',
      '/operations': 'http://localhost:8989',
      '/session': 'http://localhost:8989',
      '/run-scenario': 'http://localhost:8989',
    }
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})

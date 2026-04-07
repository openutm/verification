/// <reference types="vitest" />
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Backend URL - defaults to localhost for local dev, but can be overridden
// for Docker container development where backend runs in a separate container
const backendUrl = process.env.VITE_BACKEND_URL || 'http://localhost:8989'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': backendUrl,
      '/health': backendUrl,
      '/operations': backendUrl,
      '/session': backendUrl,
      '/run-scenario': backendUrl,
      '/run-scenario-async': backendUrl,
      '/run-scenario-events': backendUrl,
      '/stop-scenario': backendUrl,
      '/reports': backendUrl,
    }
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})

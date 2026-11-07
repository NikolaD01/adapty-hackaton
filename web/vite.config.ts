import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      'feature-signal-sdk': fileURLToPath(new URL('../sdk/js/src/index.ts', import.meta.url)),
    },
  },
  server: {
    fs: { allow: [fileURLToPath(new URL('..', import.meta.url))] },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})

/// <reference types="vitest/config" />

import { fileURLToPath } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

const envDir = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, envDir)
  const apiBaseUrl = env.VITE_API_BASE_URL || 'http://localhost:8000'

  return {
    envDir,
    plugins: [react()],
    server: {
      proxy: {
        '/api': apiBaseUrl,
        '/health': apiBaseUrl,
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
    },
  }
})

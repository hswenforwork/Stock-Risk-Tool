/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  build: {
    // 策略編輯器（Blockly）約 720 kB，已拆成延遲載入的獨立檔案
    chunkSizeWarningLimit: 800,
  },
  server: {
    // 開發時把 /api 轉給本機的 FastAPI 後端
    proxy: { '/api': 'http://localhost:8000' },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
  },
})

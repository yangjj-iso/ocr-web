import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

const outputDir = process.env.VITE_OUTPUT_DIR || 'dist'
const devApiTarget = process.env.VITE_DEV_API_PROXY_TARGET || process.env.VITE_API_BASE_URL || 'http://localhost:8000'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: devApiTarget,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: outputDir,
    emptyOutDir: true,
  },
})

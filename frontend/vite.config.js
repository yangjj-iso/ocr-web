import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

const outputDir = process.env.VITE_OUTPUT_DIR || 'dist'
const controlPlaneTarget =
  process.env.VITE_DEV_API_PROXY_TARGET ||
  process.env.VITE_CONTROL_PLANE_API_BASE_URL ||
  'http://localhost:8080'

const aiApiTarget =
  process.env.VITE_AI_API_PROXY_TARGET ||
  process.env.VITE_AI_API_BASE_URL ||
  'http://localhost:8001'

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
      '/api/admin': { target: aiApiTarget, changeOrigin: true },
      '/api/archive': { target: aiApiTarget, changeOrigin: true },
      '/api/operator': { target: aiApiTarget, changeOrigin: true },
      '/api': { target: controlPlaneTarget, changeOrigin: true },
    },
  },
  build: {
    outDir: outputDir,
    emptyOutDir: true,
  },
})

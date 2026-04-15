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
      '/api/archive-control': {
        target: controlPlaneTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/archive-control/, '/api/archive'),
      },
      '/api/admin/tenants': { target: controlPlaneTarget, changeOrigin: true },
      '/api/admin/users': { target: controlPlaneTarget, changeOrigin: true },
      '/api/admin/operation-logs': { target: controlPlaneTarget, changeOrigin: true },
      '/api/tenants': { target: controlPlaneTarget, changeOrigin: true },
      '/api/operator/my-quota': { target: controlPlaneTarget, changeOrigin: true },
      '/api/operator/my-quota/consume': { target: controlPlaneTarget, changeOrigin: true },
      '/api/admin': { target: aiApiTarget, changeOrigin: true },
      '/api/archive': { target: aiApiTarget, changeOrigin: true },
      '/api/operator': { target: aiApiTarget, changeOrigin: true },
      '/api': { target: controlPlaneTarget, changeOrigin: true },
    },
  },
  build: {
    outDir: outputDir,
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('pdfjs-dist')) return 'vendor-pdf'
          if (id.includes('chart.js') || id.includes('vue-chartjs')) return 'vendor-charts'
          if (/[\\/]node_modules[\\/](vue|vue-router|pinia)[\\/]/.test(id)) return 'vendor-core'
          if (id.includes('lucide-vue-next')) return 'vendor-ui'
          return 'vendor'
        },
      },
    },
  },
})

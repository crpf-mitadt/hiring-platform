import process from 'node:process'
import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'
import { defineConfig } from 'vite'

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8010'

export default defineConfig({
  plugins: [
    frappeui({
      frappeProxy: false,
      jinjaBootData: false,
      buildConfig: false
    }),
    vue()
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': apiProxyTarget
    }
  },
  optimizeDeps: {
    esbuildOptions: {
      external: ['~icons/lucide/*']
    }
  },
  test: {
    environment: 'jsdom'
  }
})

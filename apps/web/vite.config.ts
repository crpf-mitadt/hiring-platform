import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'
import { defineConfig } from 'vite'

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
      '/api': 'http://localhost:8000'
    }
  },
  test: {
    environment: 'jsdom'
  }
})

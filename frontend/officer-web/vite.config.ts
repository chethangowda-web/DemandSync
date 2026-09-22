import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// VITE_BASE=/officer/ for the production build served by the API; '/' for local dev.
// VITE_PROXY_TARGET points dev at an API other than a local one (e.g. a deployed instance).
// /health is proxied as well as /api: the sign-in screen probes it for the platform status lamp.
const target = process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000'
const proxy = { target, changeOrigin: true }

export default defineConfig({
  base: process.env.VITE_BASE || '/',
  plugins: [react()],
  server: { host: '127.0.0.1', port: 3000, proxy: { '/api': proxy, '/health': proxy } }
})

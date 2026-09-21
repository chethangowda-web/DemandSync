import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// VITE_BASE=/officer/ for the production build served by the API; '/' for local dev.
export default defineConfig({
  base: process.env.VITE_BASE || '/',
  plugins: [react()],
  server: { host: '127.0.0.1', port: 3000, proxy: { '/api': 'http://127.0.0.1:8000' } }
})

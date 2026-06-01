import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'

// Resolve backend port from env/local/api.env so `npm run dev` works without
// the Makefile. Falls back to process.env, then 8000.
function backendPortFromEnvFile(): string | undefined {
  const envPath = path.resolve(__dirname, '../../env/local/api.env')
  try {
    const text = fs.readFileSync(envPath, 'utf8')
    const m = text.match(/^\s*(?:export\s+)?NOIRCODE_API_FIBER_PORT\s*=\s*"?([^"\s]+)"?\s*$/m)
    return m?.[1]
  } catch {
    return undefined
  }
}

const backendPort =
  process.env.NOIRCODE_API_FIBER_PORT ??
  backendPortFromEnvFile() ??
  '8000'

// The SPA always calls a relative /api/v1 base (same origin), so it works
// unchanged behind the prod nginx proxy. In dev the vite server proxies /api
// to the backend: localhost for host runs (run-local), or the backend
// container when the frontend itself runs in Docker (PROXY_TARGET is set).
const proxyTarget =
  process.env.NOIRCODE_API_PROXY_TARGET ?? `http://localhost:${backendPort}`

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: proxyTarget, changeOrigin: true },
    },
  },
  define: {
    'import.meta.env.VITE_API_BASE': JSON.stringify('/api/v1'),
  },
})

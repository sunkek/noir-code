import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'

// Resolve backend port from env/local/api.env so `npm run dev` works without
// the Makefile. Falls back to process.env, then 8000.
function backendPortFromEnvFile(): string | undefined {
  const envPath = path.resolve(import.meta.dirname, '../../env/local/api.env')
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

export default defineConfig(({ isSsrBuild }) => ({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: proxyTarget, changeOrigin: true },
    },
  },
  // The content pages and the 404 page are HTML entries of their own, so they
  // share App.css with the app and ship as plain, crawlable HTML. nginx serves
  // them by path (/how-it-works -> how-it-works.html; .docker/nginx.conf).
  // The SSR build (the prerender's server entry) takes its input from --ssr.
  build: isSsrBuild ? {} : {
    rolldownOptions: {
      input: {
        main: path.resolve(import.meta.dirname, 'index.html'),
        howItWorks: path.resolve(import.meta.dirname, 'how-it-works.html'),
        howItWorksRu: path.resolve(import.meta.dirname, 'ru/how-it-works.html'),
        notFound: path.resolve(import.meta.dirname, '404.html'),
      },
    },
  },
  define: {
    'import.meta.env.VITE_API_BASE': JSON.stringify('/api/v1'),
  },
}))

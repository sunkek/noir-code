// Server entry for the build-time prerender (scripts/prerender.mjs). Built with
// `vite build --ssr` into dist-ssr/ and never shipped to the browser.
import { StrictMode } from 'react'
import { renderToString } from 'react-dom/server'
import App from './App'

export function render(): string {
  return renderToString(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

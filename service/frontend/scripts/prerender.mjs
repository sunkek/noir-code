// Render the app's first screen into dist/index.html, after `vite build` (the
// client bundle) and `vite build --ssr` (dist-ssr/entry-server.js).
//
// The page used to ship a separate static snapshot for crawlers, which the app
// replaced on load: a visible jump from one layout to another. Now the first
// paint is the app itself, main.tsx hydrates it, and crawlers read the same
// page visitors see.
import { readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const file = fileURLToPath(new URL('../dist/index.html', import.meta.url))
const { render } = await import(new URL('../dist-ssr/entry-server.js', import.meta.url).href)

const html = await readFile(file, 'utf8')
const empty = '<div id="root"></div>'
if (html.split(empty).length !== 2) {
  throw new Error(`prerender: expected exactly one ${empty} in dist/index.html`)
}
await writeFile(file, html.replace(empty, `<div id="root">${render()}</div>`))
console.log('prerender: dist/index.html')

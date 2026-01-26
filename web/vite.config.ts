import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import type { Plugin } from 'vite'
import fs from 'node:fs/promises'
import path from 'node:path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
    localNewsData(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    fs: {
      allow: [
        // 允许 dev server 读取仓库根目录下的 NewsReport/data
        fileURLToPath(new URL('..', import.meta.url)),
      ],
    },
  },
})

function localNewsData(): Plugin {
  const repoRoot = fileURLToPath(new URL('..', import.meta.url))
  const dataDir = path.join(repoRoot, 'NewsReport', 'data')

  async function readJsonFile(filename: string): Promise<string | null> {
    const fullPath = path.join(dataDir, filename)
    try {
      return await fs.readFile(fullPath, 'utf-8')
    } catch {
      return null
    }
  }

  return {
    name: 'local-news-data',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const url = req.url ?? ''
        if (url === '/api/news/index.json') {
          const body = await readJsonFile('index.json')
          if (!body) {
            res.statusCode = 404
            res.end('index.json not found')
            return
          }
          res.setHeader('Content-Type', 'application/json; charset=utf-8')
          res.end(body)
          return
        }

        const m = url.match(/^\/api\/news\/(\d{4}-\d{2}-\d{2})\.json$/)
        if (m) {
          const body = await readJsonFile(`${m[1]}.json`)
          if (!body) {
            res.statusCode = 404
            res.end('day json not found')
            return
          }
          res.setHeader('Content-Type', 'application/json; charset=utf-8')
          res.end(body)
          return
        }

        next()
      })
    },
  }
}

import { defineConfig, searchForWorkspaceRoot } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'

const DATA_DIR = path.resolve(__dirname, '../data')
const EVALUATION_DIR = path.resolve(__dirname, '../evaluation')

function serveRepoDirectory(routePrefix, baseDir) {
  return {
    name: `serve-repo-${routePrefix}-directory`,
    configureServer(server) {
      server.middlewares.use(`/${routePrefix}`, (req, res, next) => {
        if (req.method !== 'GET' && req.method !== 'HEAD') {
          next()
          return
        }

        const requestPath = decodeURIComponent((req.url || '/').split('?')[0])
        const relativePath = requestPath.replace(/^\/+/, '')
        const absolutePath = path.resolve(baseDir, relativePath)

        if (!absolutePath.startsWith(baseDir)) {
          res.statusCode = 403
          res.end('Forbidden')
          return
        }

        fs.stat(absolutePath, (error, stats) => {
          if (error || !stats.isFile()) {
            next()
            return
          }

          const ext = path.extname(absolutePath).toLowerCase()
          const contentTypes = {
            '.json': 'application/json; charset=utf-8',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.tif': 'image/tiff',
            '.tiff': 'image/tiff',
            '.csv': 'text/csv; charset=utf-8'
          }

          res.setHeader('Content-Type', contentTypes[ext] || 'application/octet-stream')
          fs.createReadStream(absolutePath).pipe(res)
        })
      })
    }
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    serveRepoDirectory('data', DATA_DIR),
    serveRepoDirectory('evaluation', EVALUATION_DIR)
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
    fs: {
      allow: [
        searchForWorkspaceRoot(process.cwd()),
        DATA_DIR,
        EVALUATION_DIR
      ]
    }
  }
})

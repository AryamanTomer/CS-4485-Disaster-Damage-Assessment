import { defineConfig, searchForWorkspaceRoot } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'

const DATA_DIR = path.resolve(__dirname, '../data')

function serveRepoDataDirectory() {
  return {
    name: 'serve-repo-data-directory',
    configureServer(server) {
      server.middlewares.use('/data', (req, res, next) => {
        if (req.method !== 'GET' && req.method !== 'HEAD') {
          next()
          return
        }

        const requestPath = decodeURIComponent((req.url || '/').split('?')[0])
        const relativePath = requestPath.replace(/^\/+/, '')
        const absolutePath = path.resolve(DATA_DIR, relativePath)

        if (!absolutePath.startsWith(DATA_DIR)) {
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
            '.tiff': 'image/tiff'
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
  plugins: [react(), serveRepoDataDirectory()],
  server: {
    fs: {
      allow: [
        searchForWorkspaceRoot(process.cwd()),
        DATA_DIR
      ]
    }
  }
})

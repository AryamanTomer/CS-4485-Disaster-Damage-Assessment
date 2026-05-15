/**
 * API URL rules:
 *
 * - `npm run dev`: defaults to `/api` (Vite proxies to http://127.0.0.1:8000 — see vite.config.js).
 *   Start the API in another terminal from repo root:
 *   python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
 *
 * - Override dev/prod base: set VITE_API_BASE_URL (e.g. `http://127.0.0.1:8000` or `http://3.129.36.25/api`).
 *
 * - Production Docker build: VITE_API_BASE_URL=/api (nginx proxies to FastAPI).
 */
const isDev = import.meta.env.DEV;
const raw = import.meta.env.VITE_API_BASE_URL;

export const API_BASE_URL = (() => {
  if (raw != null && String(raw).trim() !== '') {
    return String(raw).replace(/\/$/, '');
  }
  if (isDev) {
    return '/api';
  }
  return '/api';
})();

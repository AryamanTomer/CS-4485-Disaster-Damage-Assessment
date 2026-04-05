/**
 * API URL rules (keep local setup simple):
 *
 * - `npm run dev` (development): ALWAYS uses http://127.0.0.1:8000 — no frontend .env required.
 *   Start the API in another terminal: python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
 *
 * - Production build (e.g. Docker): uses VITE_API_BASE_URL, default `/api` (nginx proxies to FastAPI).
 */
const isDev = import.meta.env.DEV;
const raw = import.meta.env.VITE_API_BASE_URL;

export const API_BASE_URL = (() => {
  if (isDev) {
    return 'http://127.0.0.1:8000';
  }
  const base = raw == null || raw === '' ? '/api' : raw;
  return base.replace(/\/$/, '');
})();

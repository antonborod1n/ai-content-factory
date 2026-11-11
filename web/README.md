# Operator UI (Stage 8a)

Local Vite + React + TypeScript + MUI panel. It only calls FastAPI — no
provider keys and no generation logic.

```bash
# API must already be up: docker compose up --build -d
cd web
npm run dev
```

`npm install` only the first time or after dependency changes.

Open http://127.0.0.1:15173. Vite proxies `/api` and `/health` to
`http://127.0.0.1:8000`. Override with `VITE_API_BASE_URL` only if the
proxy is not used; then FastAPI CORS (`APP_CORS_ORIGINS`) must allow the
Vite origin.

Full startup order: [GUIDE.md §2](../GUIDE.md).

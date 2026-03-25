# Anti Money Laundering System (Frontend)

Professional light-themed analyst console built with React + Vite.

## Run

```bash
npm install
npm run dev
```

## Backend connectivity

By default, the dev server proxies:

- `/api/*` → `http://localhost:8000`
- `/health` → `http://localhost:8000`

If you deploy the frontend separately (no proxy), set `VITE_API_BASE_URL`:

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

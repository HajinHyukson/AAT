# Vercel + Cloudflare Tunnel Deployment

This is the low-cost deployment path for the dashboard:

- Vercel hosts the Next.js dashboard.
- The server computer keeps Postgres and FastAPI.
- Cloudflare Tunnel exposes only FastAPI, not Postgres.
- The browser talks to Vercel only. Vercel server code forwards API requests with `AAT_API_KEY`.

## Secrets

Generate one shared API key and use the same value on the server and in Vercel:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Vercel environment variables for the `dashboard` project:

```text
AAT_DASHBOARD_USER=aat
AAT_DASHBOARD_PASSWORD=<shared-dashboard-password>
AAT_API_BASE_URL=<cloudflare-tunnel-url>
AAT_API_KEY=<shared-api-key>
```

Server environment variables for FastAPI:

```bash
export AAT_API_KEY="<shared-api-key>"
export DATABASE_URL="postgresql+psycopg://attribution:attribution@localhost:55432/attribution"
```

Do not set `NEXT_PUBLIC_API_BASE_URL` in Vercel. The production dashboard should not expose the
raw API host to the browser.

## Server

Run Postgres as usual:

```bash
cd ~/work/AAT
docker compose up -d postgres
```

Run FastAPI bound to localhost:

```bash
cd ~/work/AAT
source .venv/bin/activate
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Verify local health:

```bash
curl http://127.0.0.1:8000/health
curl -H "X-AAT-API-Key: <shared-api-key>" "http://127.0.0.1:8000/universe?limit=1"
```

## Cloudflare Tunnel

For a quick pilot without a domain, run:

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

Use the generated `https://*.trycloudflare.com` URL as `AAT_API_BASE_URL` in Vercel. This URL is
temporary and changes when the tunnel restarts.

For a stable setup, buy or use a domain in Cloudflare DNS, then create a named tunnel:

```bash
cloudflared tunnel login
cloudflared tunnel create aat-api
cloudflared tunnel route dns aat-api api.example.com
```

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: <tunnel-uuid>
credentials-file: /home/<user>/.cloudflared/<tunnel-uuid>.json

ingress:
  - hostname: api.example.com
    service: http://127.0.0.1:8000
  - service: http_status:404
```

Run it:

```bash
cloudflared tunnel run aat-api
```

Then set `AAT_API_BASE_URL=https://api.example.com` in Vercel.

## Vercel

Import the GitHub repo into Vercel with:

```text
Root Directory: dashboard
Framework: Next.js
Install Command: npm install
Build Command: npm run build
```

Add the four Vercel environment variables from the Secrets section for Production and Preview.
Redeploy after changing any env var.

## Validation

After deployment:

```bash
curl https://<vercel-app-url>/api/aat/health
curl -I https://<vercel-app-url>/
```

Expected behavior:

- The dashboard asks for Basic Auth.
- `/api/aat/health` returns the FastAPI health response through Vercel.
- Dashboard data loads after signing in.
- Browser devtools show dashboard API calls going to `/api/aat/*`, not to the raw tunnel URL.
- Postgres port `55432` remains private to the server computer.

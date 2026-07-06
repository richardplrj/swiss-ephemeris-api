# Deploying — free, always-on, no rate limits

The whole app is a single Docker container with the ~6 MB ephemeris files baked
in, so it runs anywhere that runs a container. Below are the best **free** options
in rough order of "professional + generous" → "zero-friction, no credit card."

All of these satisfy the requirement of **no rate limiting**. Where a platform
scales to zero when idle, the first request after a nap pays a one-time cold
start — a `/health` keep-warm cron removes it (also free).

> ⚠️ **The one thing to set:** an unlimited public endpoint invites scraping.
> None of these bill you for *requests*, but a runaway could exceed a free
> compute quota. Cap **max instances** (shown below) as a spend circuit-breaker.
> That bounds cost without rate-limiting any real user.

---

## Option A — Google Cloud Run (recommended)

Genuine always-free tier (2M requests, 360k GB-s, 180k vCPU-s / month — far more
than this workload), native Python speed, real filesystem for the `.se1` files,
no per-request limit. Needs a Google account with billing enabled (free tier is
still free; billing is just on file).

```bash
# one-time
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com

# build + deploy straight from source (Cloud Build makes the image)
gcloud run deploy swiss-ephemeris-api \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 3 \
  --memory 512Mi \
  --cpu 1
```

`--max-instances 3` is the cost ceiling. `--allow-unauthenticated` makes it public.
The command prints your live URL.

**Keep it warm (free, kills cold starts)** — add `.github/workflows/keepwarm.yml`:

```yaml
name: keep-warm
on:
  schedule: [{ cron: "*/5 * * * *" }]   # every 5 min
jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - run: curl -fsS https://YOUR-SERVICE-URL/health
```

---

## Option B — Fly.io (always-on, no cold start)

A single `shared-cpu-1x` 256 MB machine runs 24/7 with no scale-to-zero. Fly's
free allowance has tightened since 2024, so budget a **~$2/mo** floor. Pick this
if zero cold-start matters more than being strictly $0.

```bash
fly launch --no-deploy          # generates fly.toml from the Dockerfile
fly deploy
```

In `fly.toml`, set `min_machines_running = 1` and an internal port of `8080`.

---

## Option C — Render (no credit card)

Easiest signup. The **free web service sleeps after 15 min idle** (≈30–50 s cold
start), so pair it with the same keep-warm cron as Option A.

1. Push this repo to GitHub.
2. Render → **New → Web Service** → pick the repo.
3. Environment **Docker** (it detects the `Dockerfile`). No start command needed.
4. Instance type **Free**. Deploy.

## Option D — Koyeb (no credit card)

One free web service, Docker-native, global edge. Similar idle behavior to Render.

1. Koyeb → **Create Service → GitHub** → this repo → Dockerfile builder.
2. Port `8080`, instance **Free**, deploy.

## Option E — Hugging Face Spaces (no credit card)

Free CPU, Docker Spaces, great for a public demo.

1. Create a **Space** → SDK **Docker**.
2. Push this repo to it. Add one line to the top of `README.md`'s front-matter
   or a `README` header with `app_port: 8080` (HF reads `app_port`).
3. It builds the Dockerfile and serves it publicly.

---

## Environment variables (optional)

| Var | Default | Purpose |
|-----|---------|---------|
| `PORT` | `8080` | Injected by most PaaS; the container honors it. |
| `SWISSAPI_EPHE_PATH` | `/app/ephe` | Where the `.se1` files live (set in the Dockerfile). |
| `SWISSAPI_SOURCE_URL` | GitHub placeholder | **Set this to your real repo URL** so the AGPL source link in every response and `/license` is correct. |

```bash
# Cloud Run example:
gcloud run deploy swiss-ephemeris-api --source . \
  --set-env-vars SWISSAPI_SOURCE_URL=https://github.com/YOU/YOUR_REPO ...
```

---

## Sanity check after deploy

```bash
curl https://YOUR-URL/health
curl "https://YOUR-URL/v1/chart?datetime=2000-01-01T12:00:00Z&lat=28.6&lon=77.2" | head -c 400
```

`meta.source` in the response should point at your public repo — that link is
what keeps the AGPL happy.

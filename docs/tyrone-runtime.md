# Tyrone Runtime Profile

This document is a server-side profile for later validation. Do not run it from the local Mac workspace.

## Ports

- PostgreSQL: `127.0.0.1:5433`
- Hiring Platform API: `127.0.0.1:8010`
- Hiring Platform frontend: `127.0.0.1:5173`
- Chandra OCR: `127.0.0.1:18083`
- Gemma primary: `127.0.0.1:24181`
- Gemma fallback: `127.0.0.1:24182`

Do not use `8000` or `3000` for this platform on Tyrone.

## Repository Paths

- Platform: `/home/danish/projects/Hiring/hiring-platform`
- Screening engine: `/home/danish/projects/Hiring/hiring-screening-engine`

The platform must consume the existing model services through the screening engine. It must not launch, restart, kill,
or duplicate Chandra/Gemma processes.

## Platform Environment

Use `.env.tyrone.example` as a non-secret template. It documents:

- `HIRING_DATABASE_URL`
- `HIRING_SCREENING_PROVIDER=engine`
- `HIRING_SCREENING_ENGINE_ROOT=/home/danish/projects/Hiring/hiring-screening-engine`
- `HIRING_SCREENING_ENGINE_PYTHON=uv run python`
- `HIRING_SCREENING_CHANDRA_BASE_URL=http://127.0.0.1:18083`
- `HIRING_SCREENING_CHANDRA_MODEL=chandra-ocr-2-q8`
- `HIRING_SCREENING_GEMMA_BASE_URL=http://127.0.0.1:24181/v1`
- `HIRING_SCREENING_GEMMA_FALLBACK_BASE_URL=http://127.0.0.1:24182/v1`
- `HIRING_SCREENING_GEMMA_API_KEY=no-key`
- `HIRING_SCREENING_GEMMA_MODEL=/home/danish/models/gemma4-12B/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`
- `HIRING_SCREENING_GEMMA_RESUME_MAX_TOKENS=16384`
- `HIRING_SCREENING_CHANDRA_OCR_RETRY_MAX_TOKENS=8192`
- `HIRING_SCREENING_PIPELINE_DEBUG_RAW_RESPONSES=false`

`no-key` is the current local llama.cpp convention. The configuration still supports real secret values later.

## Engine Environment Bridge

The stable engine source currently supports these environment variables:

- `CHANDRA_BASE_URL`
- `CHANDRA_MODEL`
- `GEMMA_BASE_URL`
- `GEMMA_API_KEY`
- `GEMMA_MODEL`
- `GEMMA_RESUME_MAX_TOKENS`
- `CHANDRA_OCR_RETRY_MAX_TOKENS`
- `PIPELINE_DEBUG_RAW_RESPONSES`
- `LLM_REQUEST_TIMEOUT_SECONDS`

The platform maps its `HIRING_SCREENING_*` settings into those names only for the engine subprocess. The stable engine
does not currently consume `CHANDRA_API_KEY`; the platform keeps `HIRING_SCREENING_CHANDRA_API_KEY` available for future
auth support but intentionally does not pass unsupported `CHANDRA_API_KEY` to the engine.

## Gemma Fallback

The provider uses the primary Gemma slot first. If resume structuring fails with `GEMMA_UNAVAILABLE`, and
`HIRING_SCREENING_GEMMA_FALLBACK_BASE_URL` is configured, it retries resume structuring once against the fallback slot.

Fallback is infrastructure failover only. It must not retry or reinterpret:

- deterministic scoring outcomes
- candidate eligibility results
- malformed business data
- unsupported approved rubric payloads
- canonical engine schema validation failures

`ScreeningRun.model_endpoint_slot` records `primary` or `fallback` where Gemma was used. Candidate-safe responses do not
include this field.

## Frontend Environment

For SSH-tunnel access from the Mac later:

- Mac `localhost:5173` tunnels to Tyrone `127.0.0.1:5173`
- Mac `localhost:8010` tunnels to Tyrone `127.0.0.1:8010`

Use:

```bash
VITE_API_BASE_URL=http://localhost:8010
VITE_API_PROXY_TARGET=http://localhost:8010
```

Do not configure public exposure, NGINX, Cloudflare, or system services in this milestone.

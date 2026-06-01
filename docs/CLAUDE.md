# CLAUDE.md

Guidance for Claude Code (and humans) working in this repo.

## What this is

**NoiR Code** — a QR-like visual encoder where the code **is** a noir comic panel. Text
is wrapped in a `MAGIC/LEN/payload/CRC32` frame, Reed–Solomon encoded, interleaved across
a grid of hatched tonal cells (Channel A) plus a bottom tonal strip mirroring the header
(Channel B), inside a black border frame used as the detection fiducial. Decode rectifies
the frame, normalizes levels, samples the grid, and RS-corrects. The art (halftone
cityscape, hatching) is cosmetic — only cell centers carry data.

## Layout

- `service/python` — deterministic encode/decode **core** + CLI (`noir`) + FastAPI imaging
  sidecar (`noir-api`). Source of truth; byte-stable for a given (text, config, seed).
- `service/backend` — Go (Fiber, ports & adapters) gateway. Public, stateless; proxies
  encode/decode to the sidecar (which owns the OpenCV pipeline).
- `service/frontend` — React + Vite SPA (encode / decode / camera scan, EN-RU).
- `deploy/` — docker-compose + `k8s/` (Kustomize). `env/example/` — config reference.

## Commands

```bash
# Python core + sidecar (run in service/python)
uv sync --extra api
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy

# Go gateway (service/backend)
go build ./... && go vet ./... && go test ./...

# Frontend (service/frontend)
npm ci && npm run lint && npm run build

# Whole stack
make run-local   # host: sidecar + gateway + vite
make up          # Docker: http://localhost:8080
```

## Invariants (don't break)

- The encoder is **byte-stable** for a given (text, config, seed) — tests assert on it.
  A panel encoded by one version must keep decoding.
- All tunables live in `service/python/.../config.py` — no magic numbers elsewhere.
- Robustness comes from the **frame fiducial + Reed–Solomon + cross-channel checksum**,
  not the styling. Styling that breaks a decode gate is a bug.
- Service names (`imaging`, `backend`, `frontend`) are load-bearing: the frontend nginx
  proxies `/api`→`backend`, the gateway calls `imaging` — keep them in compose + k8s.

# Contributing to NoiR Code

Thanks for your interest! NoiR Code is a small full-stack project: a Python
encode/decode core + FastAPI sidecar, a Go (Fiber) gateway, and a React/Vite SPA.

## Layout

See the [README](README.md#layout). The deterministic encode/decode core lives in
`service/python`; everything else is plumbing around it.

## Dev setup

```bash
# Python core + imaging sidecar
cd service/python && uv sync --extra api
uv run pytest -q && uv run ruff check . && uv run mypy

# Go gateway
cd service/backend && go build ./... && go vet ./...

# Frontend
cd service/frontend && npm install && npm run build && npm run lint
```

Run the whole stack with `make run-local` (host) or `make up` (Docker).

## Before opening a PR

- Python changes **must** keep `ruff check`, `ruff format --check`, `mypy`, and
  `pytest` green (CI enforces this). Add a test for any behavior change to the core.
- Go: `go build ./... && go vet ./...`.
- Frontend: `npm run build && npm run lint`.
- The encoder is byte-stable for a given (text, config, seed) — don't break the
  fixtures without a deliberate, documented reason.

## Format / wire compatibility

The on-panel format is a cross-cutting contract (documented in
`service/python/README.md`). A panel encoded by one version should still decode later
— flag any format change explicitly in the PR.

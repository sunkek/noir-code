# Security Policy

## Reporting a vulnerability

Please report security issues privately via GitHub's **Report a vulnerability**
(Security → Advisories) on this repository, rather than opening a public issue.
We'll acknowledge and respond as soon as we can.

## Scope & threat model

NoiR Code is a **visual data encoder**, not a secure container:

- Panels are **encoded, not encrypted** — anyone who can read a panel can recover its
  payload. Do not put secrets in a panel.
- The public API (`/encode`, `/decode`) is intentionally **unauthenticated** and
  carries no user data or persistence.
- The decode endpoint runs OpenCV on uploaded images; deployments should keep the
  request body limit in place (default 20 MB) and rate-limiting enabled.

Most relevant reports concern the **service** (the Go gateway, the Python imaging
sidecar, dependencies, container images), not the encoding scheme itself.

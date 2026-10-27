# Deploy NoiR Code

Production runs as a docker compose stack on `sunn-agorabot` (23.88.106.36),
behind that host's shared Traefik: imaging / backend / frontend, defined in
`deploy/docker-compose.prod.yml` and installed at `/opt/noircode`.

Only the frontend is exposed; its nginx serves the SPA and proxies `/api` to the
`backend` service, which calls `imaging` — all over the project's own network,
so the service names (`imaging`, `backend`, `frontend`) must not change.

Public URL: **https://noir-code.suncake.xyz** (proxied by Cloudflare; the A
record points at the host). Traefik's `letsencrypt` resolver issues the origin
certificate through a Cloudflare DNS-01 challenge. Camera scanning needs HTTPS,
which this covers.

## Layout on the host

```
/opt/noircode/
  docker-compose.prod.yml   # copy of deploy/docker-compose.prod.yml
  .env                      # IMAGING_TAG / BACKEND_TAG / FRONTEND_TAG — CI rewrites them
/opt/ci-deploy.sh           # forced command for the CI deploy key
```

The GHCR packages are public, so no registry login is needed.

## Deploy by hand

```bash
ssh sunn-agorabot
cd /opt/noircode
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --wait
```

Swagger is at `/api/v1/docs`.

## Continuous deploy

Pushes to `main` deploy via the `deploy` job in `.github/workflows/images.yml`.
It SSHes in as `deploy` with a key that `authorized_keys` pins to
`command="/opt/ci-deploy.sh noircode",restrict`, and sends only
`NAME_TAG=<sha>` pairs for the images that were rebuilt. The script refuses
anything else, writes the tags into `.env`, pulls and runs `up -d --wait`. A
leaked key can therefore only redeploy existing image tags of this app.

Repo secrets: `DEPLOY_HOST`, `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS`. Without
`DEPLOY_SSH_KEY` the job no-ops and stays green.

The host rate-limits SSH (`ufw limit`): about six connections in quick
succession are refused for a minute. One deploy is one connection.

## Notes

- The stack is stateless — no volumes, DB, or broker.

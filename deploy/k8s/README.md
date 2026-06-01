# Deploy NoiR Code to k3s

Three Deployments (imaging / backend / frontend) + Services + one Traefik Ingress.
Only the frontend is exposed; its nginx serves the SPA and proxies `/api` to the
`backend` Service, which calls the `imaging` Service — all over cluster DNS, so the
Service names (`imaging`, `backend`, `frontend`) must not change.

## 1. Build + publish images (GHCR)

Push to GitHub; the `build-images` workflow builds and pushes:

```
ghcr.io/<owner>/noircode-imaging
ghcr.io/<owner>/noircode-backend
ghcr.io/<owner>/noircode-frontend
```

Make those three packages **public** (GitHub → package → Package settings →
Change visibility) so k3s can pull without credentials. If you keep them private,
create a pull secret and reference it:

```bash
kubectl -n noircode create secret docker-registry ghcr \
  --docker-server=ghcr.io --docker-username=<user> --docker-password=<PAT-with-read:packages>
# then add `imagePullSecrets: [{name: ghcr}]` to each Deployment's pod spec.
```

## 2. Point the manifests at your cluster

Edit `kustomization.yaml` — replace `REPLACE_OWNER` (lowercase GitHub owner) in the
three image entries, or:

```bash
cd deploy/k8s
kustomize edit set image \
  noircode-imaging=ghcr.io/<owner>/noircode-imaging:<sha> \
  noircode-backend=ghcr.io/<owner>/noircode-backend:<sha> \
  noircode-frontend=ghcr.io/<owner>/noircode-frontend:<sha>
```

Edit `ingress.yaml`:
- `REPLACE_HOST` → your hostname (e.g. `noir.example.com`), in both the `tls` and
  `rules` sections.
- TLS: keep the `cert-manager.io/cluster-issuer: <name>` annotation if ESS uses
  cert-manager; otherwise delete it and uncomment the Traefik certresolver line.
  (Check which you have: `kubectl get clusterissuers` → cert-manager; else Traefik
  is doing ACME.)

## 3. Apply

```bash
kubectl apply -k deploy/k8s
kubectl -n noircode rollout status deploy/imaging deploy/backend deploy/frontend
kubectl -n noircode get ingress
```

Then open `https://<host>`. Swagger at `https://<host>/api/v1/docs`.

## Continuous deploy

After the first manual `kubectl apply -k` (which creates the namespace + resources),
pushes to `main` auto-deploy via the `deploy` job in `.github/workflows/images.yml`:
it pins each Deployment to the freshly-built image SHA and rolls out.

Enable it with one repo secret — a base64 kubeconfig whose current context targets
this cluster:

```bash
base64 -w0 < /path/to/sunn-chat.kubeconfig    # copy output
# GitHub → repo Settings → Secrets and variables → Actions → New secret
#   Name: KUBECONFIG_B64    Value: <the base64 blob>
```

Without the secret the deploy job no-ops (stays green). Scope the kubeconfig's
ServiceAccount to the `noircode` namespace if you want to limit CI's blast radius.

## Notes

- The stack is stateless — no PVCs, DB, or broker.
- Camera scanning needs HTTPS; the cert-manager/Traefik TLS above covers it.
- `kubectl kustomize deploy/k8s` renders the full manifest set for inspection.

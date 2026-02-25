# AWS K3s Deployment

This directory contains production manifests for running backend services on K3s.

## 1. Prerequisites

- K3s cluster on AWS
- `kubectl` access
- `ingress-nginx` installed
- `cert-manager` installed (optional but recommended)
- External managed data services configured:
  - PostgreSQL (RDS) for `core` + `chat`
  - Redis (ElastiCache)
  - Chroma endpoint
  - DynamoDB

## 2. Configure Secrets

1. Copy `secrets.example.yaml` to `secrets.yaml`.
2. Replace every placeholder with real values, including Cloudinary credentials:
   - `CLOUDINARY_CLOUD_NAME`
   - `CLOUDINARY_API_KEY`
   - `CLOUDINARY_API_SECRET`
3. Apply secrets:

```bash
kubectl apply -f deploy/k3s/secrets.yaml
```

## 3. Configure Non-Secret Settings

Update `configmaps.yaml` values for your domain and managed service endpoints.

## 4. Deploy

```bash
kubectl apply -k deploy/k3s
kubectl apply -f deploy/k3s/migrate-job.yaml
```

## 5. Verify

```bash
kubectl -n coc get pods
kubectl -n coc get ingress
kubectl -n coc logs deploy/core
```

## 6. Vercel Frontend Settings

In Vercel project environment variables:

- `VITE_API_URL=https://api.coc.example.com/api`
- `VITE_CHAT_URL=wss://api.coc.example.com/ws/chat`
- `VITE_WS_URL=wss://api.coc.example.com/ws/chat`
- `VITE_NOTIFICATIONS_WS_URL=wss://api.coc.example.com/ws/notifications`
- `VITE_AI_URL=https://api.coc.example.com/ai`
- Firebase `VITE_FIREBASE_*` values

For cookie auth across Vercel and API domains, keep backend config:

- `JWT_COOKIE_SECURE=true`
- `JWT_COOKIE_SAMESITE=None`
- CORS/CSRF origins set to your Vercel domain

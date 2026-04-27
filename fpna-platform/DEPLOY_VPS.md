# FPNA Deployment (Linux VPS, no domain)

This deploys:
- `web` (frontend, Nginx) on port `80`
- `api` (FastAPI backend) on internal port `8001`
- Docker images from Docker Hub (`fpna-web`, `fpna-api`)

## 1) VPS prerequisites

Install Docker + Compose plugin:

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
```

## 2) Copy project and configure backend env

```bash
git clone <your-repo-url> fpna-platform
cd fpna-platform
cp backend/.env.example backend/.env
```

Edit `backend/.env` for production:
- `DEBUG=False`
- `SECRET_KEY=<strong-random-secret>`
- `DATABASE_SERVER=<your-sqlserver-host-or-ip>`
- `DATABASE_PORT=1433`
- `DATABASE_NAME=<db-name>`
- `DATABASE_USER=<db-user>`
- `DATABASE_PASSWORD=<db-password>`
- `CORS_ORIGINS=http://<your-vps-ip>`

## 3) Build and run

```bash
export DOCKERHUB_NAMESPACE=<your-dockerhub-username>
export IMAGE_TAG=latest
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

## 4) Verify

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f web
```

Open in browser:
- `http://<your-vps-ip>/`

## 5) Updates

```bash
git pull
export DOCKERHUB_NAMESPACE=<your-dockerhub-username>
export IMAGE_TAG=latest
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

## 6) Optional firewall

```bash
sudo ufw allow 80/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

## GitHub Actions secrets (CI/CD)

Set these repository secrets:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN` (Docker Hub access token)
- `AZURE_VM_HOST`
- `AZURE_VM_USER`
- `AZURE_VM_SSH_KEY`
- `AZURE_VM_SSH_PORT` (optional, default 22)
- `AZURE_APP_DIR` (optional, default `~/fpna-platform`)

# QRATOR - CI/CD Deployment Guide

## Overview
This guide explains how to deploy the QRATOR Django application using Docker containers with automated CI/CD pipeline.

## Files Created for Production Deployment

### 1. Docker Configuration
- **`Dockerfile.prod`** - Multi-stage production Dockerfile
- **`.dockerignore`** - Optimizes Docker build context

### 2. CI/CD Pipeline
- **`.github/workflows/docker-ci.yml`** - GitHub Actions workflow

### 3. Production Deployment Files
- **`docker-compose.prod.yml`** - Production-ready Docker Compose
- **`.env.prod`** - Environment variables template
- **`nginx.conf`** - Nginx configuration (already exists)

## Setup Instructions

### Step 1: Docker Hub Setup
1. Create a Docker Hub account if you don't have one
2. Create a new repository named `qrator`
3. Note your Docker Hub username

### Step 2: GitHub Repository Setup
1. Push your code to GitHub
2. Go to repository Settings → Secrets and variables → Actions
3. Add these repository secrets:
   - `DOCKER_USERNAME`: Your Docker Hub username
   - `DOCKER_PASSWORD`: Your Docker Hub password or access token

### Step 3: Update Configuration Files

#### A. Update GitHub Actions Workflow
Edit `.github/workflows/docker-ci.yml`:
```yaml
env:
  REGISTRY: docker.io
  IMAGE_NAME: your-dockerhub-username/qrator  # Change this
```

#### B. Update Production Docker Compose
Edit `docker-compose.prod.yml`:
```yaml
services:
  web:
    image: your-dockerhub-username/qrator:latest  # Change this
```

#### C. Configure Production Environment
Copy and configure the environment file:
```bash
cp .env.prod .env
```
Edit `.env` with your actual values:
- Change `your_secure_password_here` to a strong password
- Update `your-very-long-and-secure-secret-key-here`
- Set your domain in `ALLOWED_HOSTS`
- Update admin credentials

### Step 4: Deploy to Another System

On the target system, you only need these files:
1. `docker-compose.prod.yml`
2. `.env` (configured)
3. `nginx.conf`

#### Deployment Commands:
```bash
# 1. Clone or copy the required files
mkdir qrator-deploy
cd qrator-deploy

# Copy the three required files here

# 2. Pull and start the application
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d

# 3. Check status
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs
```

## CI/CD Pipeline Features

### Automatic Triggers:
- **Push to main/develop**: Builds and pushes Docker image
- **Pull Request**: Tests code without pushing
- **Release**: Creates versioned tags

### Pipeline Steps:
1. **Test**: Runs Python tests
2. **Build**: Creates multi-stage Docker image
3. **Push**: Uploads to Docker Hub
4. **Tag**: Creates semantic version tags

### Image Tags:
- `latest`: Latest main branch
- `develop`: Latest develop branch
- `v1.0.0`: Version tags
- `main-sha123`: Commit-specific tags

## Production Features

### Health Checks:
- **Database**: PostgreSQL readiness check
- **Web App**: Django admin accessibility
- **Nginx**: Proxy server response

### Security:
- Multi-stage Docker builds (smaller final image)
- Non-root user where possible
- Read-only configuration files
- Environment variable isolation

### Reliability:
- Automatic restart policies
- Service dependencies with health checks
- Volume persistence for database and static files

## Monitoring and Maintenance

### Check Application Status:
```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs web
```

### Update Application:
```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

### Backup Database:
```bash
docker exec postgres_db pg_dump -U postgres postgres > backup.sql
```

### Restore Database:
```bash
docker exec -i postgres_db psql -U postgres postgres < backup.sql
```

## Troubleshooting

### Common Issues:
1. **Image not found**: Check Docker Hub credentials and image name
2. **Database connection failed**: Verify environment variables
3. **Static files 404**: Ensure volume mapping is correct
4. **Permission denied**: Check file permissions and user context

### Logs:
```bash
# All services
docker compose -f docker-compose.prod.yml logs

# Specific service
docker compose -f docker-compose.prod.yml logs web
docker compose -f docker-compose.prod.yml logs db
docker compose -f docker-compose.prod.yml logs nginx
```

## Security Best Practices

1. **Never commit `.env` files** to version control
2. **Use strong passwords** and rotate regularly
3. **Enable HTTPS** in production
4. **Regularly update** base Docker images
5. **Monitor Docker Hub** for security updates
6. **Use Docker secrets** for sensitive data in production

## Next Steps

1. Set up SSL/TLS certificates for HTTPS
2. Configure backup strategies
3. Set up monitoring and alerting
4. Consider using Docker Swarm or Kubernetes for scaling
5. Implement CI/CD for database migrations

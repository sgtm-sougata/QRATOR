# QRATOR - Docker Installation Package

This folder contains all the files needed to deploy the QRATOR Django application on any system with Docker and Docker Compose.

## Files Included

- **`docker-compose.prod.yml`** - Production Docker Compose configuration
- **`.env`** - Environment variables (configure this before deployment)
- **`nginx.conf`** - Nginx reverse proxy configuration
- **`DEPLOYMENT.md`** - Complete deployment documentation

## Quick Deployment

The docker-compose.prod.yml file is already configured to use:
- **Image**: `sougatamaity/qrator:main`
- **Username**: `sougatamaity`

1. **Configure Environment**
   ```bash
   # Edit the .env file with your settings

- **Database setup** - PostgreSQL container automatically starts
- **Django migrations** - Database schema applied automatically
- **Superuser creation** - Admin user created from .env file
- **Static files collection** - CSS/JS files collected and served automatically
- **Nginx configuration** - Reverse proxy and static file serving
- **Health checks** - All services monitored for readiness

## 📱 Access Your Application

- **Main Application**: http://localhost
- **Admin Panel**: http://localhost/admin/

## 👤 Default Credentials

Check the `.env` file for your credentials:
- Username: ``
- Password: ``

## 🔧 Management Commands

```bash
# Start services
docker compose -f docker-compose.prod.yml up -d

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Stop services
docker compose -f docker-compose.prod.yml down

# Restart services  
docker compose -f docker-compose.prod.yml restart

# Check status
docker compose -f docker-compose.prod.yml ps
```

## 📁 File Structure

```
docker-installation/
├── docker-compose.prod.yml    # Docker services
├── .env                       # Environment variables
├── nginx.conf                 # Nginx configuration
└── README.md                  # This file
```

## 🎯 Production Features

- ✅ Multi-stage Docker build for optimization
- ✅ PostgreSQL database with persistent storage
- ✅ Nginx reverse proxy with static file serving
- ✅ Health checks for all services
- ✅ Automatic superuser creation
- ✅ Static files automatically collected
- ✅ Ready for localhost deployment

**No manual commands required - everything works automatically!**!

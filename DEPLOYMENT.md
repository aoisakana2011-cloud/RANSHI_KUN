# RANSHI_KUN Cloud Deployment Guide

## Overview
This guide covers deploying RANSHI_KUN menstrual cycle prediction system to cloud platforms (AWS, Google Cloud, Azure).

## Prerequisites

### Required Tools
- Docker and Docker Compose
- Cloud provider CLI (AWS CLI, gcloud, or Azure CLI)
- SSL certificate (for production)
- Domain name (optional but recommended)

### Environment Setup
1. Copy `.env.production` to `.env.local` and update with your values
2. Ensure all required environment variables are set
3. Test locally first: `docker-compose -f docker-compose.production.yml up`

## Cloud Provider Options

### 1. AWS Deployment

#### Prerequisites
```bash
# Install AWS CLI
pip install awscli

# Configure credentials
aws configure
```

#### Deployment Steps
```bash
# Make deploy script executable
chmod +x deploy.sh

# Deploy to AWS
./deploy.sh aws production your-domain.com
```

#### AWS Services Used
- **ECS** (Elastic Container Service) - Container orchestration
- **ECR** (Elastic Container Registry) - Docker registry
- **RDS** (Relational Database Service) - PostgreSQL database
- **ELB** (Elastic Load Balancer) - Load balancing
- **Route 53** - DNS management
- **ACM** (Certificate Manager) - SSL certificates

#### Manual AWS Setup
```bash
# Create ECR repository
aws ecr create-repository --repository-name ranshi-kun

# Build and push image
docker build -t ranshi-kun:latest .
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-west-2.amazonaws.com
docker tag ranshi-kun:latest <account-id>.dkr.ecr.us-west-2.amazonaws.com/ranshi-kun:latest
docker push <account-id>.dkr.ecr.us-west-2.amazonaws.com/ranshi-kun:latest
```

### 2. Google Cloud Deployment

#### Prerequisites
```bash
# Install Google Cloud SDK
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init
```

#### Deployment Steps
```bash
# Deploy to Google Cloud
./deploy.sh gcp production your-domain.com
```

#### GCP Services Used
- **Cloud Run** - Serverless container platform
- **Cloud SQL** - Managed PostgreSQL database
- **Cloud Build** - CI/CD pipeline
- **Cloud DNS** - DNS management
- **Cloud Load Balancing** - Load balancing

#### Manual GCP Setup
```bash
# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Deploy to Cloud Run
gcloud run deploy ranshi-kun \
  --image gcr.io/PROJECT-ID/ranshi-kun:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### 3. Azure Deployment

#### Prerequisites
```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
az login
```

#### Deployment Steps
```bash
# Deploy to Azure
./deploy.sh azure production your-domain.com
```

#### Azure Services Used
- **Container Instances** - Container hosting
- **Azure Database for PostgreSQL** - Managed database
- **Azure Container Registry** - Docker registry
- **Application Gateway** - Load balancing and SSL
- **Azure DNS** - DNS management

## Configuration

### Environment Variables
Key environment variables for production:

```bash
# Flask Configuration
FLASK_ENV=production
SECRET_KEY=your-super-secret-key

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Security
ADMIN_API_TOKEN=your-admin-token
SESSION_COOKIE_SECURE=True

# SSL/HTTPS
SSL_CERT_PATH=/path/to/cert.pem
SSL_KEY_PATH=/path/to/key.pem
```

### Security Configuration
- HTTPS enforced in production
- Security headers configured
- Rate limiting applied
- SSL certificates auto-renewed

## Monitoring and Logging

### Application Logs
```bash
# View application logs
docker-compose logs -f web

# View nginx logs
docker-compose logs -f nginx
```

### Monitoring Setup
- Prometheus metrics collection
- Grafana dashboards
- Error tracking with Sentry
- Health check endpoints

### Backup Strategy
- Daily database backups
- Automated backup rotation
- Cloud storage for backup files

## SSL/HTTPS Setup

### Automatic SSL (Let's Encrypt)
```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### Manual SSL
1. Obtain SSL certificate from your provider
2. Place files in `nginx/ssl/` directory
3. Update `nginx.conf` with certificate paths

## Performance Optimization

### Database Optimization
- Connection pooling configured
- Query optimization
- Regular maintenance

### Application Optimization
- Gzip compression enabled
- Static file caching
- CDN integration ready

### Scaling Options
- Horizontal scaling with load balancer
- Database read replicas
- Caching layer with Redis

## Troubleshooting

### Common Issues

#### Database Connection
```bash
# Check database connectivity
docker-compose exec web python -c "from app.extensions import db; print(db.engine.execute('SELECT 1').scalar())"
```

#### SSL Issues
```bash
# Check SSL certificate
openssl s_client -connect your-domain.com:443
```

#### Performance Issues
```bash
# Monitor resource usage
docker stats
```

### Health Checks
```bash
# Application health
curl https://your-domain.com/health

# Database health
curl https://your-domain.com/health/db
```

## Maintenance

### Updates
```bash
# Pull latest changes
git pull origin main

# Rebuild and redeploy
docker-compose -f docker-compose.production.yml up -d --build
```

### Database Migrations
```bash
# Run migrations
docker-compose exec web python -c "from app.migrations import migrate; migrate()"
```

### Backup Restoration
```bash
# Restore from backup
docker-compose exec db psql -U postgres -d ranshi_kun < backup.sql
```

## Security Best Practices

1. **Regular Updates**: Keep Docker images and dependencies updated
2. **Access Control**: Use strong passwords and 2FA
3. **Network Security**: Configure firewalls and security groups
4. **Monitoring**: Set up alerts for suspicious activity
5. **Backup**: Regular automated backups
6. **SSL**: Always use HTTPS in production

## Support

For deployment issues:
1. Check logs: `docker-compose logs`
2. Verify environment variables
3. Test locally first
4. Check cloud provider status

## Cost Optimization

- Use appropriate instance sizes
- Enable auto-scaling
- Monitor resource usage
- Use reserved instances for long-term deployments

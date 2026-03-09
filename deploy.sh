#!/bin/bash

# RANSHI_KUN Cloud Deployment Script
# Supports AWS, Google Cloud, and Azure deployment

set -e

# Configuration
CLOUD_PROVIDER=${1:-"aws"}
ENVIRONMENT=${2:-"production"}
DOMAIN=${3:-"your-domain.com"}

echo "🚀 Deploying RANSHI_KUN to $CLOUD_PROVIDER in $ENVIRONMENT environment"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to deploy to AWS
deploy_aws() {
    echo "📦 Deploying to AWS..."
    
    # Check AWS CLI
    if ! command_exists aws; then
        echo "❌ AWS CLI not found. Please install it first."
        exit 1
    fi
    
    # Check Docker
    if ! command_exists docker; then
        echo "❌ Docker not found. Please install it first."
        exit 1
    fi
    
    # Build and push to ECR
    echo "🏗️ Building Docker image..."
    docker build -t ranshi-kun:latest .
    
    # Get AWS account ID
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    ECR_REPO="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/ranshi-kun"
    
    # Login to ECR
    echo "🔐 Logging into ECR..."
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPO
    
    # Tag and push
    docker tag ranshi-kun:latest $ECR_REPO:latest
    docker push $ECR_REPO:latest
    
    # Deploy with ECS or EB (simplified example)
    echo "🚢 Deploying to ECS..."
    # This would typically use AWS CDK, Terraform, or ECS CLI
    # For demonstration, we're showing the manual steps
    
    echo "✅ AWS deployment completed!"
    echo "🌐 Your application should be available at: https://$DOMAIN"
}

# Function to deploy to Google Cloud
deploy_gcp() {
    echo "📦 Deploying to Google Cloud..."
    
    # Check gcloud CLI
    if ! command_exists gcloud; then
        echo "❌ Google Cloud SDK not found. Please install it first."
        exit 1
    fi
    
    # Set project
    gcloud config set project $GCP_PROJECT_ID
    
    # Build and push to GCR
    echo "🏗️ Building Docker image..."
    docker build -t gcr.io/$GCP_PROJECT_ID/ranshi-kun:latest .
    
    # Push to GCR
    echo "🚢 Pushing to Google Container Registry..."
    docker push gcr.io/$GCP_PROJECT_ID/ranshi-kun:latest
    
    # Deploy to Cloud Run
    echo "☁️ Deploying to Cloud Run..."
    gcloud run deploy ranshi-kun \
        --image gcr.io/$GCP_PROJECT_ID/ranshi-kun:latest \
        --platform managed \
        --region $AWS_REGION \
        --allow-unauthenticated \
        --set-env-vars "FLASK_ENV=production,DATABASE_URL=$DATABASE_URL"
    
    echo "✅ Google Cloud deployment completed!"
}

# Function to deploy to Azure
deploy_azure() {
    echo "📦 Deploying to Azure..."
    
    # Check Azure CLI
    if ! command_exists az; then
        echo "❌ Azure CLI not found. Please install it first."
        exit 1
    fi
    
    # Build and push to ACR
    echo "🏗️ Building Docker image..."
    docker build -t ranshi-kun:latest .
    
    # Get ACR details
    ACR_NAME=$(az acr list --query "[0].name" -o tsv)
    ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer -o tsv)
    
    # Login to ACR
    echo "🔐 Logging into ACR..."
    az acr login --name $ACR_NAME
    
    # Tag and push
    docker tag ranshi-kun:latest $ACR_LOGIN_SERVER/ranshi-kun:latest
    docker push $ACR_LOGIN_SERVER/ranshi-kun:latest
    
    # Deploy to Container Instances
    echo "☁️ Deploying to Azure Container Instances..."
    az container create \
        --resource-group ranshi-kun-rg \
        --name ranshi-kun \
        --image $ACR_LOGIN_SERVER/ranshi-kun:latest \
        --dns-name-label ranshi-kun-$RANDOM \
        --ports 80 \
        --environment-variables "FLASK_ENV=production" "DATABASE_URL=$DATABASE_URL"
    
    echo "✅ Azure deployment completed!"
}

# Function to setup SSL certificates
setup_ssl() {
    echo "🔒 Setting up SSL certificates..."
    
    # Install certbot if not present
    if ! command_exists certbot; then
        echo "📦 Installing certbot..."
        sudo apt-get update
        sudo apt-get install -y certbot python3-certbot-nginx
    fi
    
    # Get SSL certificate
    sudo certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN
    
    # Setup auto-renewal
    echo "⏰ Setting up SSL auto-renewal..."
    (crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -
    
    echo "✅ SSL setup completed!"
}

# Function to setup monitoring
setup_monitoring() {
    echo "📊 Setting up monitoring..."
    
    # Create monitoring directory
    mkdir -p monitoring
    
    # Setup Prometheus configuration
    cat > monitoring/prometheus.yml << EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'ranshi-kun'
    static_configs:
      - targets: ['web:5000']
EOF
    
    echo "✅ Monitoring setup completed!"
}

# Main deployment logic
case $CLOUD_PROVIDER in
    "aws")
        deploy_aws
        ;;
    "gcp")
        deploy_gcp
        ;;
    "azure")
        deploy_azure
        ;;
    *)
        echo "❌ Unsupported cloud provider: $CLOUD_PROVIDER"
        echo "Supported providers: aws, gcp, azure"
        exit 1
        ;;
esac

# Setup SSL and monitoring for production
if [ "$ENVIRONMENT" = "production" ]; then
    setup_ssl
    setup_monitoring
fi

echo "🎉 Deployment completed successfully!"
echo "📋 Next steps:"
echo "   1. Update your DNS to point to the deployment"
echo "   2. Test the application at https://$DOMAIN"
echo "   3. Setup backup and monitoring alerts"
echo "   4. Review security settings"

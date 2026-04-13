#!/bin/bash

# Quick Docker Build and Push Script
# Simple version for fast deployment

# set -e

# Configuration - UPDATE THESE
DOCKER_USERNAME="sougatamaity"
IMAGE_NAME="qrator"
TAG="main"
DOCKERFILE="Dockerfile.prod"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Get Docker credentials
# echo "Please enter your Docker Hub credentials:"
# echo -n "Username: "
# read DOCKER_USERNAME
# echo -n "Password/Token: "
# read -s DOCKER_PASSWORD
# echo ""

# Build and push
print_status "Building Docker image..."
docker build -f $DOCKERFILE -t $DOCKER_USERNAME/$IMAGE_NAME:$TAG .

print_status "Logging into Docker Hub..."
echo $DOCKER_PASSWORD | docker login -u $DOCKER_USERNAME --password-stdin

print_status "Pushing image to Docker Hub..."
docker push $DOCKER_USERNAME/$IMAGE_NAME:$TAG

print_success "Image pushed successfully: $DOCKER_USERNAME/$IMAGE_NAME:$TAG"

# Logout
# docker logout

print_success "Done! Update docker-compose.prod.yml with: $DOCKER_USERNAME/$IMAGE_NAME:$TAG"

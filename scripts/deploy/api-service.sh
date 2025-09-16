#!/bin/bash

# Load environment variables
export $(grep -v '^#' ../.env | xargs)

# Set base directory
base_dir=$ROOT

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== API Service Deployment Script ===${NC}"

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Build and deploy API service only
cd $base_dir

print_status "Building API service image..."
if docker build -f docker/dockerfile/api-service.Dockerfile \
    -t ${REGISTRY_URL}/api-service:${API_SERVICE_VERSION} \
    application/api-service/; then
    print_status "API service image built successfully"
else
    print_error "Failed to build API service image"
    exit 1
fi

# Check if registry is running
if curl -f http://${REGISTRY_URL}/v2/ >/dev/null 2>&1; then
    print_status "Pushing API service image..."
    docker push ${REGISTRY_URL}/api-service:${API_SERVICE_VERSION}
fi

print_status "Updating API service..."
if docker service inspect ${RABBITMQ_STACK_NAME}_api-service >/dev/null 2>&1; then
    docker service update --image ${REGISTRY_URL}/api-service:${API_SERVICE_VERSION} \
        ${RABBITMQ_STACK_NAME}_api-service
    print_status "API service updated successfully!"
else
    print_error "API service not found. Deploy the full RabbitMQ system first."
    exit 1
fi

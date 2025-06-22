#!/bin/bash

# Load environment variables
export $(grep -v '^#' ../.env | xargs)

# Set base directory
base_dir=$ROOT

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Airflow Deployment Script ===${NC}"
echo -e "${BLUE}Registry: ${REGISTRY_URL}${NC}"
echo -e "${BLUE}Airflow Version: ${AIRFLOW_VERSION}${NC}"
echo -e "${BLUE}Root Directory: ${ROOT}${NC}"

# Function to print status messages
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Change to the root directory
cd $ROOT

# Step 1: Build the peakairflow Docker image
print_status "Building peakairflow Docker image..."
docker build \
    --build-arg AIRFLOW_VERSION=${AIRFLOW_VERSION} \
    --no-cache \
    -f docker/dockerfile/airflow.Dockerfile \
    -t peakairflow:${AIRFLOW_VERSION} \
    -t ${REGISTRY_URL}/peakairflow:${AIRFLOW_VERSION} \
    .

if [ $? -ne 0 ]; then
    print_error "Failed to build Docker image"
    exit 1
fi

print_status "Successfully built ${REGISTRY_URL}/peakairflow:${AIRFLOW_VERSION}"

# Step 2: Push the image to registry
print_status "Pushing image to registry..."
docker push ${REGISTRY_URL}/peakairflow:${AIRFLOW_VERSION}

if [ $? -ne 0 ]; then
    print_error "Failed to push Docker image to registry"
    exit 1
fi

print_status "Successfully pushed image to registry"

# Step 3: Deploy Airflow stack
print_status "Deploying Airflow stack..."

# Export environment variables for docker-compose
export REGISTRY_URL=${REGISTRY_URL}
export AIRFLOW_VERSION=${AIRFLOW_VERSION}
export AIRFLOW_PROJ_DIR=${AIRFLOW_PROJ_DIR}
export AIRFLOW_UID=${AIRFLOW_UID}
export ROOT=${ROOT}
export AIRFLOW_USER=${AIRFLOW_USER}
export AIRFLOW_POSTGRES_PASSWORD=${AIRFLOW_POSTGRES_PASSWORD}
export AIRFLOW_PASSWORD=${AIRFLOW_PASSWORD}
export AIRFLOW_EMAIL=${AIRFLOW_EMAIL}
export AIRFLOW_DEPLOY_NODE_ROLE=${AIRFLOW_DEPLOY_NODE_ROLE}

# Deploy the stack using Docker Compose
docker stack deploy \
    --compose-file docker/compose/airflow.yml \
    ${AIRFLOW_STACK_NAME}

if [ $? -ne 0 ]; then
    print_error "Failed to deploy Airflow stack"
    exit 1
fi

print_status "Successfully deployed Airflow stack: ${AIRFLOW_STACK_NAME}"

# Step 4: Show deployment status
print_status "Checking deployment status..."
sleep 5
docker service ls --filter "label=com.docker.stack.namespace=${AIRFLOW_STACK_NAME}"

echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo -e "${GREEN}Airflow WebUI will be available at: http://localhost:8080${NC}"
echo -e "${GREEN}Default credentials: ${AIRFLOW_USER} / ${AIRFLOW_PASSWORD}${NC}"


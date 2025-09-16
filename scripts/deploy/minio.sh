#!/bin/bash

set -euo pipefail

# Deploy MinIO service
echo "Deploying MinIO service..."

# Source environment variables
export $(grep -v '^#' ../.env | xargs)
base_dir=$ROOT

# Create storage directory if it doesn't exist
mkdir -p ${base_dir}/storage/minio_data

# Set proper permissions for MinIO data directory
sudo chown -R 1000:1000 ${base_dir}/storage/minio_data

echo "Deploying MinIO stack..."
cd ${base_dir}/docker/compose
docker stack deploy -c minio.yml $MINIO_STACK_NAME

# Wait for MinIO to be ready
echo "Waiting for MinIO to be ready..."
sleep 30

# Check if MinIO is running
docker service ls | grep minio || {
    echo "Error: MinIO service failed to start"
    exit 1
}

echo "MinIO deployment completed successfully!"
echo "Access details:"
echo "  API URL: http://localhost:${MINIO_API_PORT}"
echo "  Console URL: http://localhost:${MINIO_CONSOLE_PORT}"
echo "  Root User: ${MINIO_ROOT_USER}"
echo "  Root Password: ${MINIO_ROOT_PASSWORD}"
echo ""
echo "You can access the MinIO console at: http://localhost:${MINIO_CONSOLE_PORT}"
echo "Default buckets created:"
echo "  - fitness-data"
echo "  - garmin-files" 
echo "  - processed-data"
echo "  - backups"
echo "  - user-uploads"

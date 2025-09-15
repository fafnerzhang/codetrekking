#!/bin/bash

set -euo pipefail

# Deploy database and storage infrastructure
echo "Deploying database and storage infrastructure..."

# Source environment variables
export $(grep -v '^#' ../.env | xargs)
base_dir=$ROOT

echo "1. Creating storage directories..."
mkdir -p ${base_dir}/storage/postgres_data
mkdir -p ${base_dir}/storage/minio_data

echo "2. Setting permissions..."
sudo chown -R 999:999 ${base_dir}/storage/postgres_data
sudo chown -R 1000:1000 ${base_dir}/storage/minio_data

echo "3. Deploying PostgreSQL..."
cd ${base_dir}/docker/compose
docker stack deploy -c postgres.yml $POSTGRES_STACK_NAME

echo "4. Deploying MinIO..."
docker stack deploy -c minio.yml $MINIO_STACK_NAME

echo "5. Waiting for services to be ready..."
sleep 45

echo "6. Checking service status..."
docker service ls | grep -E "(postgres|minio)" || {
    echo "Warning: Some services may not have started properly"
    docker service ls
}

echo ""
echo "==================================="
echo "Database and Storage Deployment Complete!"
echo "==================================="
echo ""
echo "PostgreSQL Details:"
echo "  Host: localhost"
echo "  Port: ${POSTGRES_PORT}"
echo "  Database: ${POSTGRES_DB}"
echo "  User: ${POSTGRES_USER}"
echo "  Connection: psql -h localhost -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d ${POSTGRES_DB}"
echo ""
echo "MinIO Details:"
echo "  API URL: http://localhost:${MINIO_API_PORT}"
echo "  Console URL: http://localhost:${MINIO_CONSOLE_PORT}"
echo "  Root User: ${MINIO_ROOT_USER}"
echo "  Root Password: ${MINIO_ROOT_PASSWORD}"
echo ""
echo "Created MinIO buckets:"
echo "  - fitness-data"
echo "  - garmin-files"
echo "  - processed-data"
echo "  - backups"
echo "  - user-uploads"
echo ""
echo "Next steps:"
echo "  1. Access MinIO console: http://localhost:${MINIO_CONSOLE_PORT}"
echo "  2. Connect to PostgreSQL: psql -h localhost -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d ${POSTGRES_DB}"
echo "  3. Update your application configuration to use these services"

#!/bin/bash

set -euo pipefail

# Deploy PostgreSQL service
echo "Deploying PostgreSQL service..."

# Source environment variables
export $(grep -v '^#' ../.env | xargs)
base_dir=$ROOT

# Create storage directory if it doesn't exist
mkdir -p ${base_dir}/storage/postgres_data

# Set proper permissions for PostgreSQL data directory
sudo chown -R 999:999 ${base_dir}/storage/postgres_data

echo "Deploying PostgreSQL stack..."
cd ${base_dir}/docker/compose
docker stack deploy -c postgres.yml $POSTGRES_STACK_NAME

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
sleep 45

# Test connection using Docker
echo "Testing PostgreSQL connection..."
for i in {1..10}; do
    if docker exec $(docker ps -q -f name=postgres) pg_isready -U "$POSTGRES_USER" > /dev/null 2>&1; then
        echo "PostgreSQL is ready!"
        break
    else
        echo "Waiting for PostgreSQL... (attempt $i/10)"
        sleep 10
    fi
done

# Check if PostgreSQL is running
docker service ls | grep postgres || {
    echo "Error: PostgreSQL service failed to start"
    exit 1
}

echo "PostgreSQL deployment completed successfully!"
echo "Connection details:"
echo "  Host: localhost"
echo "  Port: ${POSTGRES_PORT}"
echo "  Database: ${POSTGRES_DB}"
echo "  User: ${POSTGRES_USER}"
echo "  Password: ${POSTGRES_PASSWORD}"
echo ""
echo "You can connect using: psql -h localhost -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d ${POSTGRES_DB}"

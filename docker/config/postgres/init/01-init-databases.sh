#!/bin/bash
set -e

echo "Starting database initialization..."

# Wait for PostgreSQL to be ready
until pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do
  echo "Waiting for PostgreSQL to be ready..."
  sleep 2
done

echo "PostgreSQL is ready. Creating additional databases..."

# Create additional databases for different services
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create database for API service
    CREATE DATABASE api_service;
    GRANT ALL PRIVILEGES ON DATABASE api_service TO $POSTGRES_USER;
    
    -- Create database for PeakFlow analytics
    CREATE DATABASE peakflow_analytics;
    GRANT ALL PRIVILEGES ON DATABASE peakflow_analytics TO $POSTGRES_USER;
    
    -- Create database for user management
    CREATE DATABASE user_management;
    GRANT ALL PRIVILEGES ON DATABASE user_management TO $POSTGRES_USER;
    
    -- Create database for task management
    CREATE DATABASE task_management;
    GRANT ALL PRIVILEGES ON DATABASE task_management TO $POSTGRES_USER;
    
    -- Display created databases
    SELECT datname FROM pg_database WHERE datistemplate = false;
EOSQL

echo "Additional databases created successfully!"
echo "Available databases:"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c "\l"

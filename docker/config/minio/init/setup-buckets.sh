#!/bin/bash

# MinIO bucket initialization script
# This script creates the necessary buckets for the CodeTrekking system

set -e

echo "Setting up MinIO alias..."
mc alias set myminio http://minio:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD}

echo "Creating fitness-data bucket..."
mc mb myminio/fitness-data --ignore-existing

echo "Creating garmin-files bucket..."
mc mb myminio/garmin-files --ignore-existing

echo "Creating processed-data bucket..."
mc mb myminio/processed-data --ignore-existing

echo "Creating backups bucket..."
mc mb myminio/backups --ignore-existing

echo "Creating user-uploads bucket..."
mc mb myminio/user-uploads --ignore-existing

echo "Setting bucket policies..."
# Set public read policy for fitness-data bucket
mc anonymous set public myminio/fitness-data

echo "MinIO buckets setup completed successfully!"

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

echo -e "${BLUE}=== RabbitMQ Broker Deployment Script ===${NC}"
echo -e "${BLUE}Root Directory: ${ROOT}${NC}"
echo -e "${BLUE}RabbitMQ Host: ${RABBITMQ_HOST}${NC}"
echo -e "${BLUE}RabbitMQ Port: ${RABBITMQ_PORT}${NC}"
echo -e "${BLUE}RabbitMQ Management Port: ${RABBITMQ_MANAGEMENT_PORT}${NC}"
echo -e "${BLUE}RabbitMQ User: ${RABBITMQ_DEFAULT_USER}${NC}"
echo -e "${BLUE}RabbitMQ VHost: ${RABBITMQ_VHOST}${NC}"

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

# Create storage directories
print_status "Creating storage directories..."
mkdir -p "${ROOT}/storage/rabbitmq_data"

# Check if Docker network exists
if ! docker network ls | grep -q "codetrekking_network"; then
    print_status "Creating Docker network..."
    docker network create --driver overlay --attachable codetrekking_network
fi

# Deploy RabbitMQ broker only
print_status "Deploying RabbitMQ broker..."
cd $base_dir/docker/compose
if docker stack deploy -c rabbitmq-broker.yml rabbitmq-broker; then
    print_status "RabbitMQ broker deployment initiated successfully!"
else
    print_error "Failed to deploy RabbitMQ broker"
    exit 1
fi

print_status "Waiting for broker to start..."
sleep 30

# Check RabbitMQ health
print_status "Checking RabbitMQ health..."
for i in {1..12}; do
    if curl -s -u "${RABBITMQ_DEFAULT_USER}:${RABBITMQ_DEFAULT_PASS}" \
       "http://localhost:${RABBITMQ_MANAGEMENT_PORT}/api/overview" > /dev/null; then
        print_status "RabbitMQ is healthy and ready!"
        break
    else
        print_warning "Waiting for RabbitMQ to be ready... (attempt $i/12)"
        sleep 15
    fi
    
    if [ $i -eq 12 ]; then
        print_error "RabbitMQ failed to start properly"
        print_status "Check service logs with: docker service logs rabbitmq-broker_rabbitmq"
        exit 1
    fi
done

print_status "${GREEN}RabbitMQ broker deployment completed!${NC}"
print_status "${BLUE}RabbitMQ Management UI: http://localhost:${RABBITMQ_MANAGEMENT_PORT}${NC}"
print_status "${BLUE}Default credentials: ${RABBITMQ_DEFAULT_USER}/${RABBITMQ_DEFAULT_PASS}${NC}"

print_status "Use 'docker service ls' to check service status"
print_status "Use 'docker stack ps rabbitmq-broker' to check container status"

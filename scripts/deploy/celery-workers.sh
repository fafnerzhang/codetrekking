#!/bin/bash

# Celery Workers Deployment Script for CodeTrekking
# Deploys Celery workers, beat scheduler, and Flower monitoring

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load environment variables
if [ -f "$SCRIPT_DIR/../.env" ]; then
    # Use set -a to auto-export all variables
    set -a
    source "$SCRIPT_DIR/../.env"
    set +a
    echo "✓ Loaded environment from $SCRIPT_DIR/../.env"
else
    echo "❌ Environment file not found at $SCRIPT_DIR/../.env"
    exit 1
fi

# Validate required environment variables
required_vars=(
    "ROOT"
    "DOCKER_DIR"
    "REGISTRY_URL"
    "RABBITMQ_HOST"
    "RABBITMQ_PORT"
    "RABBITMQ_MANAGEMENT_PORT"
    "RABBITMQ_USERNAME"
    "RABBITMQ_PASSWORD"
    "RABBITMQ_VHOST"
    "RABBITMQ_URL"
)

echo "🔍 Validating required environment variables..."
missing_vars=()
for var in "${required_vars[@]}"; do
    if [ -z "${!var:-}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "❌ Missing required environment variables:"
    printf "   - %s\n" "${missing_vars[@]}"
    exit 1
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Celery Workers Deployment Script ===${NC}"
echo -e "${BLUE}Root Directory: ${ROOT}${NC}"
echo -e "${BLUE}Worker Service Version: ${WORKER_SERVICE_VERSION:-latest}${NC}"
echo -e "${BLUE}Worker Concurrency: ${WORKER_CONCURRENCY:-4}${NC}"
echo -e "${BLUE}Worker Log Level: ${WORKER_LOG_LEVEL:-INFO}${NC}"
echo -e "${BLUE}RabbitMQ Host: ${RABBITMQ_HOST}${NC}"
echo -e "${BLUE}Registry URL: ${REGISTRY_URL}${NC}"

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

# Function to check if a Docker service exists
service_exists() {
    docker service ls --format "{{.Name}}" | grep -q "^$1$"
}

# Function to check if a Docker stack exists
stack_exists() {
    docker stack ls --format "{{.Name}}" | grep -q "^$1$"
}

# Check prerequisites
print_status "🔍 Checking prerequisites..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    print_error "Docker is not running or not accessible"
    exit 1
fi

# Check if running in Swarm mode
if ! docker node ls >/dev/null 2>&1; then
    print_error "Docker Swarm is not initialized. Run: docker swarm init"
    exit 1
fi

# Check if RabbitMQ stack exists
if ! stack_exists "rabbitmq-broker"; then
    print_error "RabbitMQ broker stack is not running. Deploy it first with: make deploy-rabbitmq-broker"
    exit 1
fi

# Wait for RabbitMQ to be ready
print_status "⏳ Waiting for RabbitMQ to be ready..."
max_attempts=30
attempt=1

while [ $attempt -le $max_attempts ]; do
    if curl -s -f -u "${RABBITMQ_USERNAME}:${RABBITMQ_PASSWORD}" \
       "http://localhost:${RABBITMQ_MANAGEMENT_PORT}/api/overview" >/dev/null 2>&1; then
        print_status "✓ RabbitMQ is accessible"
        break
    else
        if [ $attempt -eq $max_attempts ]; then
            print_error "RabbitMQ is not accessible after ${max_attempts} attempts"
            print_error "Check RabbitMQ service status: docker service ls | grep rabbitmq"
            exit 1
        fi
        print_warning "Waiting for RabbitMQ... (attempt $attempt/$max_attempts)"
        sleep 5
        ((attempt++))
    fi
done

# Check/create Docker network
print_status "🌐 Checking Docker network..."
if ! docker network ls | grep -q "codetrekking"; then
    print_status "Creating Docker overlay network..."
    if ! docker network create --driver overlay --attachable codetrekking; then
        print_error "Failed to create Docker network"
        exit 1
    fi
else
    print_status "✓ Docker network 'codetrekking' exists"
fi

# Create necessary directories
print_status "📁 Creating necessary directories..."
directories=(
    "${ROOT}/storage/processed-data"
    "${GARMIN_STORAGE:-${ROOT}/storage/garmin}"
    "${ROOT}/storage/rabbitmq_data"
)

for dir in "${directories[@]}"; do
    if ! mkdir -p "$dir"; then
        print_error "Failed to create directory: $dir"
        exit 1
    fi
done

# Check and build/pull the Docker image
REGISTRY_IMAGE="${REGISTRY_URL}/peakflow-tasks:${WORKER_SERVICE_VERSION:-latest}"
print_status "🐳 Building and deploying Celery worker image: $REGISTRY_IMAGE"

# Function to build image
build_image() {
    print_status "🔨 Building peakflow-tasks image..."
    cd "${ROOT}"
    if [ -f "docker/dockerfile/peakflow-tasks.Dockerfile" ]; then
        # Force rebuild without cache to ensure latest changes
        if docker build --no-cache -f docker/dockerfile/peakflow-tasks.Dockerfile -t "$REGISTRY_IMAGE" .; then
            print_status "✓ Successfully built image"
            
            # Push to local registry if it exists
            if service_exists "registry_registry"; then
                print_status "📤 Pushing image to local registry..."
                if docker push "$REGISTRY_IMAGE"; then
                    print_status "✓ Successfully pushed to registry"
                else
                    print_warning "Failed to push to registry, but proceeding with local image"
                fi
            fi
            return 0
        else
            print_error "Failed to build Docker image"
            return 1
        fi
    else
        print_error "Dockerfile not found: docker/dockerfile/peakflow-tasks.Dockerfile"
        return 1
    fi
}

# Always build the image to ensure latest changes are included
print_status "🔨 Building fresh image with latest changes..."
if ! build_image; then
    print_error "Failed to build Docker image"
    exit 1
fi

# Remove existing stack if it exists
if stack_exists "celery-workers"; then
    print_status "🔄 Removing existing celery-workers stack..."
    docker stack rm celery-workers
    
    # Wait for services to be fully removed
    print_status "⏳ Waiting for services to be removed..."
    while docker service ls --format "{{.Name}}" | grep -q "celery-workers"; do
        sleep 2
    done
    sleep 5  # Additional wait for cleanup
fi

# Deploy Celery workers
print_status "🚀 Deploying Celery workers, beat, and flower..."
cd "${ROOT}/docker/compose"

if docker stack deploy -c celery-workers.yml celery-workers; then
    print_status "✓ Celery workers deployment initiated successfully!"
else
    print_error "Failed to deploy Celery workers"
    exit 1
fi

# Wait for services to start
print_status "⏳ Waiting for services to start..."
sleep 10

# Monitor service startup
print_status "📊 Monitoring service startup..."
services=("celery-workers_celery-worker" "celery-workers_celery-beat" "celery-workers_celery-flower")
max_wait=120
elapsed=0

while [ $elapsed -lt $max_wait ]; do
    all_running=true
    
    for service in "${services[@]}"; do
        if ! docker service ls --format "{{.Name}} {{.Replicas}}" | grep "$service" | grep -q "/.*"; then
            all_running=false
            break
        fi
    done
    
    if $all_running; then
        print_status "✓ All services are running"
        break
    fi
    
    if [ $elapsed -ge $max_wait ]; then
        print_warning "Services are taking longer than expected to start"
        break
    fi
    
    sleep 5
    elapsed=$((elapsed + 5))
done

# Check service status
print_status "📋 Current service status:"
echo
docker service ls --filter label=com.docker.stack.namespace=celery-workers

# Health check for Flower UI
print_status "🌸 Checking Flower UI availability..."
flower_attempts=24  # 2 minutes
flower_attempt=1

while [ $flower_attempt -le $flower_attempts ]; do
    if curl -s -f "http://localhost:5555" >/dev/null 2>&1; then
        print_status "✓ Flower UI is accessible"
        break
    else
        if [ $flower_attempt -eq $flower_attempts ]; then
            print_warning "Flower UI is not yet accessible, but deployment completed"
            print_warning "It may take a few more minutes to become available"
        else
            sleep 5
            ((flower_attempt++))
        fi
    fi
done

echo
print_status "${GREEN}🎉 Celery workers deployment completed!${NC}"
print_status "${BLUE}📊 Flower monitoring UI: http://localhost:5555${NC}"
print_status "${BLUE}🔑 Flower credentials: ${RABBITMQ_USERNAME}/${RABBITMQ_PASSWORD}${NC}"
print_status "${BLUE}🐰 RabbitMQ Management UI: http://localhost:${RABBITMQ_MANAGEMENT_PORT}${NC}"

echo
print_status "🛠️  Service management commands:"
print_status "  📊 Check status: docker service ls | grep celery-workers"
print_status "  📝 Check logs: docker service logs celery-workers_celery-worker"
print_status "  📈 Scale workers: docker service scale celery-workers_celery-worker=4"
print_status "  🗑️  Remove stack: docker stack rm celery-workers"

echo
print_status "🚀 Next steps:"
print_status "1. Test task submission from API service"
print_status "2. Monitor workers via Flower at http://localhost:5555"
print_status "3. Check RabbitMQ queues at http://localhost:${RABBITMQ_MANAGEMENT_PORT}"
print_status "4. View worker logs: docker service logs -f celery-workers_celery-worker"

# Final validation
print_status "🔍 Final validation:"
if curl -s -f "http://localhost:5555" >/dev/null 2>&1; then
    print_status "✅ Flower UI is accessible"
else
    print_warning "⚠️  Flower UI not yet ready (may take a few more minutes)"
fi

if curl -s -f -u "${RABBITMQ_USERNAME}:${RABBITMQ_PASSWORD}" \
   "http://localhost:${RABBITMQ_MANAGEMENT_PORT}/api/overview" >/dev/null 2>&1; then
    print_status "✅ RabbitMQ Management UI is accessible"
else
    print_warning "⚠️  RabbitMQ Management UI not accessible"
fi

print_status "🏁 Deployment script completed successfully!"

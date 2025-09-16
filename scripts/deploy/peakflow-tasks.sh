#!/bin/bash

# PeakFlow Tasks Deployment Script for CodeTrekking
# Deploys PeakFlow Tasks workers, beat scheduler, and Flower monitoring

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
    "RABBITMQ_DEFAULT_USER"
    "RABBITMQ_DEFAULT_PASS"
    "RABBITMQ_VHOST"
    "RABBITMQ_URL"
    "ELASTICSEARCH_HOST"
    "ELASTICSEARCH_USER"
    "ELASTIC_PASSWORD"
    "GARMIN_CONFIG_DIR"
    "GARMIN_DATA_DIR"
    # Phase 6: Database and encryption variables
    "DATABASE_URL"
    "POSTGRES_HOST"
    "POSTGRES_USER"
    "POSTGRES_PASSWORD"
    "POSTGRES_DB"
    "GARMIN_ENCRYPTION_KEY"
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
    
    # Special handling for GARMIN_ENCRYPTION_KEY
    if [[ " ${missing_vars[@]} " =~ " GARMIN_ENCRYPTION_KEY " ]]; then
        echo
        echo "💡 To generate a secure encryption key, run:"
        echo "   python3 -c \"import secrets, base64; print('GARMIN_ENCRYPTION_KEY=' + base64.b64encode(secrets.token_bytes(32)).decode())\""
        echo
        echo "Then add the generated key to scripts/.env"
    fi
    
    exit 1
fi

# Additional validation for encryption key format
if [[ -n "${GARMIN_ENCRYPTION_KEY:-}" ]]; then
    # Check if key looks like base64 (basic validation)
    if [[ ! "$GARMIN_ENCRYPTION_KEY" =~ ^[A-Za-z0-9+/]+=*$ ]]; then
        print_error "GARMIN_ENCRYPTION_KEY doesn't appear to be valid base64"
        echo "💡 Generate a new key with:"
        echo "   python3 -c \"import secrets, base64; print('GARMIN_ENCRYPTION_KEY=' + base64.b64encode(secrets.token_bytes(32)).decode())\""
        exit 1
    fi
    
    # Check key length (base64 encoded 32 bytes should be ~44 characters)
    if [[ ${#GARMIN_ENCRYPTION_KEY} -lt 40 ]]; then
        print_error "GARMIN_ENCRYPTION_KEY appears to be too short (should be ~44 characters for 32-byte key)"
        exit 1
    fi
    
    print_status "✓ Encryption key validation passed"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== PeakFlow Tasks Deployment Script ===${NC}"
echo -e "${BLUE}Root Directory: ${ROOT}${NC}"
echo -e "${BLUE}Worker Service Version: ${WORKER_SERVICE_VERSION:-latest}${NC}"
echo -e "${BLUE}Worker Concurrency: ${WORKER_CONCURRENCY:-4}${NC}"
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

# Check dependencies
if ! stack_exists "rabbitmq-broker"; then
    print_warning "RabbitMQ broker stack is not running. Some features may not work properly."
fi

if ! stack_exists "elk"; then
    print_warning "Elasticsearch stack is not running. Some features may not work properly."
fi

if ! stack_exists "postgres"; then
    print_warning "PostgreSQL stack is not running. Database-backed credential storage will not work."
    print_warning "Run: make deploy-postgres or scripts/deploy/postgres.sh"
fi

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
    "${GARMIN_DATA_DIR}"
    "${ROOT}/storage/processed-data"
)

for dir in "${directories[@]}"; do
    if ! mkdir -p "$dir"; then
        print_error "Failed to create directory: $dir"
        exit 1
    fi
done

# Build and push Docker image
REGISTRY_IMAGE="${REGISTRY_URL}/peakflow-tasks:${WORKER_SERVICE_VERSION:-latest}"
print_status "🐳 Building PeakFlow Tasks image: $REGISTRY_IMAGE"

# Function to build image
build_image() {
    print_status "🔨 Building peakflow-tasks image..."
    cd "${ROOT}"
    if [ -f "docker/dockerfile/peakflow-tasks.Dockerfile" ]; then
        # Build with context from repository root to access peakflow dependency
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

# Build the image
print_status "🔨 Building fresh image with latest changes..."
if ! build_image; then
    print_error "Failed to build Docker image"
    exit 1
fi

# Remove existing stack if it exists
if stack_exists "peakflow-tasks"; then
    print_status "🔄 Removing existing peakflow-tasks stack..."
    docker stack rm peakflow-tasks
    
    # Wait for services to be fully removed
    print_status "⏳ Waiting for services to be removed..."
    while docker service ls --format "{{.Name}}" | grep -q "peakflow-tasks"; do
        sleep 2
    done
    sleep 5  # Additional wait for cleanup
fi

# Deploy PeakFlow Tasks
print_status "🚀 Deploying PeakFlow Tasks..."
cd "${ROOT}/docker/compose"

if docker stack deploy -c peakflow-tasks.yml peakflow-tasks; then
    print_status "✓ PeakFlow Tasks deployment initiated successfully!"
else
    print_error "Failed to deploy PeakFlow Tasks"
    exit 1
fi

# Wait for services to start
print_status "⏳ Waiting for services to start..."
sleep 15

# Monitor service startup
print_status "📊 Monitoring service startup..."
services=("peakflow-tasks_peakflow-tasks-worker" "peakflow-tasks_peakflow-tasks-beat" "peakflow-tasks_peakflow-tasks-flower")
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
docker service ls --filter label=com.docker.stack.namespace=peakflow-tasks

echo
print_status "${GREEN}🎉 PeakFlow Tasks deployment completed!${NC}"
print_status "${BLUE}📊 Flower monitoring UI: http://localhost:5555${NC}"
print_status "${BLUE}🔑 Flower credentials: ${RABBITMQ_DEFAULT_USER}/${RABBITMQ_DEFAULT_PASS}${NC}"
print_status "${BLUE}🐰 RabbitMQ Management UI: http://localhost:${RABBITMQ_MANAGEMENT_PORT:-15672}${NC}"
print_status "${BLUE}🔍 Elasticsearch: ${ELASTICSEARCH_HOST}${NC}"

echo
print_status "🛠️  Service management commands:"
print_status "  📊 Check status: docker service ls | grep peakflow-tasks"
print_status "  📝 Check worker logs: docker service logs peakflow-tasks_peakflow-tasks-worker"
print_status "  📝 Check beat logs: docker service logs peakflow-tasks_peakflow-tasks-beat"
print_status "  📈 Scale workers: docker service scale peakflow-tasks_peakflow-tasks-worker=4"
print_status "  🗑️  Remove stack: docker stack rm peakflow-tasks"

print_status "🏁 Deployment script completed successfully!"

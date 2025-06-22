#!/bin/bash

# Source the .env file
source scripts/.env

# Access the environment variables
echo "ELASTIC_VERSION: $ELASTIC_VERSION"

# Path to the config.yaml file
CONFIG_FILE="scripts/config.yaml"

# Check if the config.yaml file exists
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Error: $CONFIG_FILE not found!"
  exit 1
fi

# Parse the "storage" property from config.yaml and create directories
BASE_DIR="storage"

STORAGE_DIRS=$(awk '/^storage:/ {flag=1; next} /^\S/ {flag=0} flag && /^  - / {print $2}' "$CONFIG_FILE")
for DIR in $STORAGE_DIRS; do
  mkdir -p "$BASE_DIR/$DIR"
  echo "Created directory: $BASE_DIR/$DIR"
done

echo "Creating swarm overlay network: codetrekking"

# Check if network already exists
if docker network ls --format "table {{.Name}}" | grep -q "^codetrekking$"; then
    echo "Network 'codetrekking' already exists"
    docker network inspect codetrekking
else
    # Create overlay network for swarm
    docker network create \
        --driver overlay \
        --attachable \
        --scope swarm \
        codetrekking
    echo "Network 'codetrekking' created successfully"
fi

echo ""
echo "Network is ready for swarm services!"
echo "You can now deploy services that use this network."

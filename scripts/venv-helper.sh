#!/bin/bash

# Virtual Environment Helper Script for CodeTrekking
# Usage: source scripts/venv-helper.sh
# Then use: venv_activate api-service

venv_activate() {
    local service_name="$1"
    local project_root="/home/aiuser/codetrekking"
    
    if [ -z "$service_name" ]; then
        echo "Usage: venv_activate <service-name>"
        echo "Available services: api-service, celery-service, peakflow"
        return 1
    fi
    
    local service_dir="$project_root/application/$service_name"
    local venv_path="$service_dir/.venv"
    
    if [ ! -d "$service_dir" ]; then
        echo "Error: Service directory '$service_dir' does not exist"
        return 1
    fi
    
    if [ ! -d "$venv_path" ]; then
        echo "Error: Virtual environment '$venv_path' does not exist"
        echo "Create it with: cd $service_dir && python -m venv .venv"
        return 1
    fi
    
    echo "Activating virtual environment for $service_name..."
    cd "$service_dir"
    source "$venv_path/bin/activate"
    
    echo "Virtual environment activated!"
    echo "Current directory: $(pwd)"
    echo "Python executable: $(which python)"
    echo "To deactivate, run: deactivate"
}

# Alias for convenience
alias venv=venv_activate

# Show available services
venv_list() {
    echo "Available services:"
    echo "  - api-service"
    echo "  - celery-service"
    echo "  - peakflow"
    echo ""
    echo "Usage: venv_activate <service-name>"
    echo "Example: venv_activate api-service"
}

echo "Virtual Environment Helper loaded!"
echo "Usage: venv_activate <service-name> or venv <service-name>"
echo "List services: venv_list"

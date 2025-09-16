#!/bin/bash
set -e

echo "=== PeakFlow Tasks Container Startup ==="
echo "Current working directory: $(pwd)"
echo "Python version: $(python --version 2>&1 || echo 'Python not found')"
echo "Python3 version: $(python3 --version 2>&1 || echo 'Python3 not found')"
echo "Virtual env Python: $(/app/.venv/bin/python --version 2>&1 || echo 'Venv Python not found')"
echo "Contents of /app:"
ls -la /app/
echo "Contents of /app/.venv/bin:"
ls -la /app/.venv/bin/
echo "PYTHONPATH: ${PYTHONPATH:-not set}"
echo "PATH: $PATH"
echo "========================================"

# Check if virtual environment exists and is working
if [ -f "/app/.venv/bin/python" ]; then
    echo "Using virtual environment Python: /app/.venv/bin/python"
    exec /app/.venv/bin/python /app/worker.py "$@"
elif which python3 >/dev/null 2>&1; then
    echo "Using system Python3"
    cd /app
    export PYTHONPATH="/app:${PYTHONPATH}"
    exec python3 worker.py "$@"
elif which python >/dev/null 2>&1; then
    echo "Using system Python"
    cd /app
    export PYTHONPATH="/app:${PYTHONPATH}"
    exec python worker.py "$@"
else
    echo "ERROR: No Python interpreter found!"
    exit 1
fi

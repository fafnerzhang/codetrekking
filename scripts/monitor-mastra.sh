#!/bin/bash

# Monitor and manage Mastra server processes
# Usage: ./monitor-mastra.sh [status|kill|restart|logs]

MASTRA_DIR="/home/aiuser/codetrekking/application/peakview/mastra"
MASTRA_PORT="4113"

case "${1:-status}" in
  "status")
    echo "=== Mastra Process Status ==="
    ps aux | grep -E "(mastra|node.*mastra)" | grep -v grep
    echo ""
    echo "=== Port Usage ==="
    netstat -tulpn | grep ":${MASTRA_PORT}"
    echo ""
    echo "=== Server Health ==="
    if curl -s "http://localhost:${MASTRA_PORT}/" > /dev/null; then
      echo "✅ Mastra server is responding on port ${MASTRA_PORT}"
    else
      echo "❌ Mastra server is not responding on port ${MASTRA_PORT}"
    fi
    ;;
  
  "kill")
    echo "🔴 Killing all Mastra processes..."
    pkill -f "mastra dev"
    pkill -f "node.*mastra"
    sleep 2
    echo "✅ Mastra processes terminated"
    ;;
  
  "restart")
    echo "🔄 Restarting Mastra server..."
    pkill -f "mastra dev"
    pkill -f "node.*mastra"
    sleep 2
    cd "$MASTRA_DIR"
    echo "📁 Starting in directory: $(pwd)"
    nohup npm run dev > /tmp/mastra.log 2>&1 &
    sleep 5
    echo "✅ Mastra server started (logs: /tmp/mastra.log)"
    tail -n 10 /tmp/mastra.log
    ;;
  
  "logs")
    echo "📄 Mastra logs (last 50 lines):"
    if [ -f "/tmp/mastra.log" ]; then
      tail -n 50 /tmp/mastra.log
    else
      echo "No log file found at /tmp/mastra.log"
    fi
    ;;
  
  *)
    echo "Usage: $0 [status|kill|restart|logs]"
    echo ""
    echo "  status   - Show process status and health"
    echo "  kill     - Kill all Mastra processes"
    echo "  restart  - Kill and restart Mastra server"
    echo "  logs     - Show recent server logs"
    ;;
esac
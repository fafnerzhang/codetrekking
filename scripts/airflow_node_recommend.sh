#!/bin/bash
# Script to determine node roles and update AIRFLOW_DEPLOY_NODE_ROLE_ROLE in scripts/.env based on node status

ENV_FILE="$(dirname "$0")/.env"

# Get the number of manager and worker nodes that are Ready and Active
MANAGER_COUNT=$(docker node ls --format '{{.ID}} {{.Hostname}} {{.Status}} {{.Availability}} {{.ManagerStatus}}' | awk '$3=="Ready" && $4=="Active" && ($5=="Leader" || $5=="Reachable")' | wc -l)
WORKER_COUNT=$(docker node ls --format '{{.ID}} {{.Hostname}} {{.Status}} {{.Availability}} {{.ManagerStatus}}' | awk '$3=="Ready" && $4=="Active" && $5==""' | wc -l)

echo "Active manager nodes: $MANAGER_COUNT"
echo "Active worker nodes: $WORKER_COUNT"

if [ "$WORKER_COUNT" -gt 0 ]; then
  echo "Recommend: Deploy Airflow on worker nodes (node.role==worker)"
  if grep -q '^AIRFLOW_DEPLOY_NODE_ROLE=' "$ENV_FILE"; then
    sed -i 's/^AIRFLOW_DEPLOY_NODE_ROLE=.*/AIRFLOW_DEPLOY_NODE_ROLE=worker/' "$ENV_FILE"
  else
    echo 'AIRFLOW_DEPLOY_NODE_ROLE=worker' >> "$ENV_FILE"
  fi
  echo "AIRFLOW_DEPLOY_NODE_ROLE set to worker in $ENV_FILE"
  exit 0
elif [ "$MANAGER_COUNT" -gt 0 ]; then
  echo "Recommend: Deploy Airflow on manager nodes (node.role==manager)"
  if grep -q '^AIRFLOW_DEPLOY_NODE_ROLE=' "$ENV_FILE"; then
    sed -i 's/^AIRFLOW_DEPLOY_NODE_ROLE=.*/AIRFLOW_DEPLOY_NODE_ROLE=manager/' "$ENV_FILE"
  else
    echo 'AIRFLOW_DEPLOY_NODE_ROLE=manager' >> "$ENV_FILE"
  fi
  echo "AIRFLOW_DEPLOY_NODE_ROLE set to manager in $ENV_FILE"
  exit 0
else
  echo "No active nodes available for deployment."
  exit 1
fi

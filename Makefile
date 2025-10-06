SCRIPTS_DIR := scripts


help:    ## Show help message.
	@sed -ne '/@sed/!s/## //p' $(MAKEFILE_LIST)

setup:  ## Run the setup script to initialize the environment
	@echo "Running setup.sh..."
	bash $(SCRIPTS_DIR)/setup.sh

deploy-airflow:    ## Deploy Airflow using the deploy script
	@echo "Running deploy/airflow.sh..."
	cd scripts/deploy && bash airflow.sh

deploy-elk:    ## Deploy Elasticsearch using the deploy script
	@echo "Running deploy/elk.sh..."
	cd scripts/deploy && bash elk.sh

deploy-potainer:    ## Deploy Potainer using the deploy script
	@echo "Running deploy/potainer.sh..."
	cd scripts/deploy && bash potainer.sh

deploy-registry:
	@echo "Running deploy/registry.sh..."
	cd scripts/deploy && bash registry.sh

deploy-rabbitmq-broker:    ## Deploy RabbitMQ broker only
	@echo "Running deploy/rabbitmq-broker.sh..."
	cd scripts/deploy && bash rabbitmq-broker.sh

deploy-postgres:    ## Deploy PostgreSQL database
	@echo "Running deploy/postgres.sh..."
	cd scripts/deploy && bash postgres.sh

deploy-minio:    ## Deploy MinIO S3-compatible storage
	@echo "Running deploy/minio.sh..."
	cd scripts/deploy && bash minio.sh

deploy-database-storage:    ## Deploy both PostgreSQL and MinIO services
	@echo "Running deploy/database-storage.sh..."
	cd scripts/deploy && bash database-storage.sh

deploy-peakflow-tasks:    ## Deploy PeakFlow Tasks distributed processing system
	@echo "Running deploy/peakflow-tasks.sh..."
	cd scripts/deploy && bash peakflow-tasks.sh

monitor-tasks:    ## Open Celery Flower monitoring interface
	@echo "📊 Opening Celery Flower monitoring..."
	@echo "🌐 http://localhost:5555"
	@command -v open >/dev/null 2>&1 && open http://localhost:5555 || echo "Open http://localhost:5555 in your browser"

scale-workers:    ## Scale PeakFlow Tasks workers
	@echo "📈 Scaling task workers to 4 replicas..."
	docker service scale peakflow-tasks_peakflow-tasks-worker=4

logs-tasks:    ## Show PeakFlow Tasks worker logs
	@echo "📋 Showing task worker logs..."
	docker service logs -f peakflow-tasks_peakflow-tasks-worker

logs-beat:    ## Show Celery beat scheduler logs  
	@echo "📋 Showing beat scheduler logs..."
	docker service logs -f peakflow-tasks_peakflow-tasks-beat

remove-peakflow-tasks:    ## Remove PeakFlow Tasks stack
	@echo "🗑️  Removing PeakFlow Tasks stack..."
	docker stack rm peakflow-tasks

# === Mastra AI Server Management ===

mastra-status:    ## Check Mastra server status and health
	@echo "🔍 Checking Mastra server status..."
	./scripts/monitor-mastra.sh status

mastra-restart:    ## Restart Mastra server cleanly
	@echo "🔄 Restarting Mastra server..."
	./scripts/monitor-mastra.sh restart

mastra-kill:    ## Kill all Mastra processes
	@echo "🔴 Killing Mastra processes..."
	./scripts/monitor-mastra.sh kill

mastra-logs:    ## Show Mastra server logs
	@echo "📄 Showing Mastra server logs..."
	./scripts/monitor-mastra.sh logs

mastra-dev:    ## Start Mastra development server
	@echo "🚀 Starting Mastra development server..."
	cd application/peakview/mastra && npm run dev
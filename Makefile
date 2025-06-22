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
SCRIPTS_DIR := scripts


help:    ## Show help message.
	@sed -ne '/@sed/!s/## //p' $(MAKEFILE_LIST)

setup:  ## Run the setup script to initialize the environment
	@echo "Running setup.sh..."
	bash $(SCRIPTS_DIR)/setup.sh

deploy-airflow:    ## Deploy Airflow using the deploy script
	@echo "Running deploy_airflow.sh..."
	cd scripts && bash deploy_airflow.sh

deploy-elk:    ## Deploy Elasticsearch using the deploy script
	@echo "Running deploy_elk.sh..."
	cd scripts && bash deploy_elk.sh

deploy-potainer:    ## Deploy Potainer using the deploy script
	@echo "Running deploy_potainer.sh..."
	cd scripts && bash deploy_potainer.sh

entry:    ## Run the entry script to start the application
	@echo "Running entry.sh..."
	bash $(SCRIPTS_DIR)/entry.sh
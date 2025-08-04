from airflow.sdk import DAG, task, Param
from datetime import datetime, timedelta
import sys
import os
from pathlib import Path
from peakflow.providers.garmin import GarminClient
from peakflow.utils import build_garmin_config, get_garmin_config_dir


# Define parameters for setup (requires password)
setup_params = {
    'user': Param(
        default='example@gmail.com',
        type='string',
        title='Garmin Connect Username',
        description='Your Garmin Connect account username'
    ),
    'password': Param(
        default='example_password',
        type='string',
        title='Garmin Connect Password',
        format='password',
        description='Your Garmin Connect account password'
    )
}

# Create setup DAG for Garmin configuration (requires password)
with DAG(
    dag_id='garmin_setup_config',
    description='Setup Garmin Connect configuration with credentials',
    schedule=None,  # Manual trigger only
    start_date=datetime(2025, 6, 1),
    catchup=False,
    tags=['garmin', 'setup', 'config', 'peakflow'],
    params=setup_params,
    default_args={
        'owner': 'airflow',
        'depends_on_past': False,
        'retries': 1,
        'retry_delay': timedelta(minutes=5),
    },
    render_template_as_native_obj=True,
) as dag:

    @task.python(task_id='build_garmin_config')
    def build_garmin_config_task(**context):
        """
        Build and save Garmin Connect configuration
        
        Args:
            **context: Airflow context containing params and execution info
            
        Returns:
            dict: Status information about the configuration setup
        """
        # Get parameters from context
        params = context.get('params', {})
        user = params.get('user', 'example@gmail.com')
        password = params.get('password', 'example_password')
        
        # Setup configuration directory
        default_config_dir = f'/opt/garmin/{user}'
        
        print(f"Setting up Garmin configuration for user: {user}")
        print(f"Configuration directory: {default_config_dir}")
        
        try:
            # Build and save configuration
            build_garmin_config(user, password, default_config_dir)
            config_dir = get_garmin_config_dir(user, default_config_dir)
            
            # Test the configuration by creating a client
            client = GarminClient.create_safe_client(config_dir)
            
            print(f"Successfully created and tested Garmin configuration for {user}")
            print(f"Configuration saved to: {config_dir}")
            
            return {
                'status': 'success',
                'user': user,
                'config_dir': config_dir,
                'message': f'Configuration successfully created and tested for {user}',
                'config_file_exists': (Path(config_dir) / "GarminConnectConfig.json").exists()
            }
            
        except Exception as e:
            print(f"Failed to setup Garmin configuration: {e}")
            return {
                'status': 'failed',
                'user': user,
                'error': str(e),
                'message': f'Failed to setup configuration for {user}: {str(e)}'
            }
    
    @task.python(task_id='verify_config')
    def verify_config_task(setup_result, **context):
        """
        Verify that the configuration was created successfully
        
        Args:
            setup_result: Result from the setup task
            **context: Airflow context
            
        Returns:
            dict: Verification results
        """
        if not setup_result or setup_result.get('status') != 'success':
            print("Setup task failed, verification skipped")
            return {
                'status': 'skipped', 
                'reason': 'setup_failed',
                'setup_result': setup_result
            }
        
        user = setup_result.get('user')
        config_dir = setup_result.get('config_dir')
        
        print(f"Verifying configuration for user: {user}")
        
        # Check if config file exists
        config_file = Path(config_dir) / "GarminConnectConfig.json"
        config_exists = config_file.exists()
        
        print(f"Configuration file exists: {config_exists}")
        print(f"Configuration file path: {config_file}")
        
        if config_exists:
            try:
                # Try to read the config file
                with open(config_file, 'r') as f:
                    import json
                    config_data = json.load(f)
                    has_credentials = 'credentials' in config_data
                    has_user = has_credentials and 'user' in config_data['credentials']
                    
                print(f"Configuration file is valid JSON: True")
                print(f"Has credentials section: {has_credentials}")
                print(f"Has user configured: {has_user}")
                
                return {
                    'status': 'success',
                    'user': user,
                    'config_dir': config_dir,
                    'config_file_exists': True,
                    'config_valid': True,
                    'has_credentials': has_credentials,
                    'has_user': has_user,
                    'message': f'Configuration verified successfully for {user}'
                }
                
            except Exception as e:
                print(f"Configuration file exists but is invalid: {e}")
                return {
                    'status': 'failed',
                    'user': user,
                    'config_dir': config_dir,
                    'config_file_exists': True,
                    'config_valid': False,
                    'error': str(e),
                    'message': f'Configuration file is corrupted for {user}'
                }
        else:
            return {
                'status': 'failed',
                'user': user,
                'config_dir': config_dir,
                'config_file_exists': False,
                'message': f'Configuration file not found for {user}'
            }

    # Define the tasks and dependencies
    setup_task = build_garmin_config_task()
    verify_task = verify_config_task(setup_task)
    
    # Set task dependencies
    setup_task >> verify_task

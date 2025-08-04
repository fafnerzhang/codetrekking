from airflow.sdk import DAG, task, Param
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
from datetime import datetime, timedelta
from peakflow.providers.garmin import GarminClient
from peakflow.utils import build_garmin_config, get_garmin_config_dir
from pathlib import Path
import os


# Define default parameters
default_params = {
    'user': Param(
        default='example@gmail.com',
        type='string',
        title='Garmin Connect Username',
        description='Your Garmin Connect account username'
    ),
    'days_to_download': Param(
        default=1,
        type='integer',
        minimum=1,
        maximum=720,
        title='Days to Download',
        description='Number of days of data to download'
    ),
    'overwrite_existing': Param(
        default=True,
        type='boolean',
        title='Overwrite Existing Files',
        description='Whether to overwrite existing downloaded files'
    )
}

# Create DAG using context manager approach
with DAG(
    dag_id='garmin_download_daily_data',
    description='Download Garmin user daily data using PeakFlow',
    schedule="@daily",
    start_date=datetime(2025, 6, 1),
    catchup=False,
    tags=['garmin', 'download', 'peakflow'],
    params=default_params,
    default_args={
        'owner': 'airflow',
        'depends_on_past': False,
        'retries': 1,
        'retry_delay': timedelta(minutes=5),
    },
    render_template_as_native_obj=True,  # Enable native object rendering for params
) as dag:

    @task.python(task_id='check_existing_activities')
    def check_existing_activities(**context):
        """
        檢查Elasticsearch中指定日期範圍內已存在的activity_id
        
        Args:
            **context: Airflow context containing params and execution info
            
        Returns:
            dict: 包含existing activity_ids的狀態信息
        """
        print("🔍 DEBUG: Starting check_existing_activities task")
        print(f"🔍 DEBUG: Full context keys: {list(context.keys())}")
        
        # Get parameters from context
        params = context.get('params', {})
        print(f"🔍 DEBUG: Received params: {params}")
        user = params.get('user', 'example@gmail.com')
        days_to_download = params.get('days_to_download', 1)
        
        print(f"🔍 DEBUG: Parsed user: {user}")
        print(f"🔍 DEBUG: Parsed days_to_download: {days_to_download}")
        
        # Calculate date range
        from datetime import date
        today = date.today()
        start_date = today - timedelta(days=days_to_download)
        end_date = today
        
        print(f"Checking existing activities for user: {user}")
        print(f"Date range: {start_date} to {end_date}")
        
    
        # Try connecting to Elasticsearch and query for existing activities
        from peakflow.storage.elasticsearch import ElasticsearchStorage
        from peakflow.storage.interface import DataType, QueryFilter
        from peakflow.const import ELASTICSEARCH_HOST, ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD
        # Initialize Elasticsearch storage
        es_storage = ElasticsearchStorage()
        # Load Elasticsearch config from Airflow Variables (recommended for Airflow)
        from airflow.models import Variable
        es_host = Variable.get('ELASTICSEARCH_HOST', default_var=ELASTICSEARCH_HOST)
        es_user = Variable.get('ELASTICSEARCH_USERNAME', default_var=ELASTICSEARCH_USER)
        es_pass = Variable.get('ELASTICSEARCH_PASSWORD', default_var=ELASTICSEARCH_PASSWORD)
        es_config = {
            'hosts': [es_host],
            'username': es_user,
            'password': es_pass,
            'verify_certs': False
        }

        if not es_storage.initialize(es_config):
            print("Warning: Could not connect to Elasticsearch, will proceed without checking")
            return {
                'status': 'elasticsearch_unavailable',
                'existing_activity_ids': set(),
                'user': user,
                'start_date': str(start_date),
                'end_date': str(end_date),
                'message': 'Elasticsearch unavailable, proceeding without duplicate check'
            }

        # Build query to get activities within the specified date range
        from datetime import datetime as dt
        start_datetime = dt.combine(start_date, dt.min.time())
        end_datetime = dt.combine(end_date, dt.max.time())

        query_filter = QueryFilter()
        query_filter.add_date_range('start_time', start=start_datetime, end=end_datetime)
        query_filter.add_term_filter('user_id', user)  # If available
        query_filter.limit = 10000  # Assume no more than 10,000 activities in this range

        # Query SESSION type data (activity data is usually stored here)
        existing_sessions = es_storage.search(DataType.SESSION, query_filter)

        # Extract activity_ids
        existing_activity_ids = set()
        for session in existing_sessions:
            activity_id = session.get('activity_id') or session.get('activityId')
            if activity_id:
                existing_activity_ids.add(str(activity_id))

        print(f"Found {len(existing_activity_ids)} existing activities in Elasticsearch")
        if existing_activity_ids:
            print(f"Existing activity IDs: {list(existing_activity_ids)[:10]}...")  # Show only first 10

        result = {
            'status': 'success',
            'existing_activity_ids': existing_activity_ids,
            'user': user,
            'start_date': str(start_date),
            'end_date': str(end_date),
            'total_existing': len(existing_activity_ids)
        }
        print(f"🔍 DEBUG: check_existing_activities returning result: {result}")
        return result

    @task.python(task_id='download_garmin_daily_data')
    def download_garmin_daily_data(existing_activities_check, **context):
        """
        Download Garmin daily data for specified user, excluding existing activities
        
        Args:
            existing_activities_check: Result from check_existing_activities task
            **context: Airflow context containing params and execution info
            
        Returns:
            dict: Status information about the download operation
        """
        print("📥 DEBUG: Starting download_garmin_daily_data task")
        print(f"📥 DEBUG: Received existing_activities_check: {existing_activities_check}")
        print(f"📥 DEBUG: existing_activities_check type: {type(existing_activities_check)}")
        
        # Get parameters from context
        params = context.get('params', {})
        print(f"📥 DEBUG: Received params: {params}")
        user = params.get('user', 'example@gmail.com')
        days_to_download = params.get('days_to_download', 1)
        overwrite_existing = params.get('overwrite_existing', False)
        
        print(f"📥 DEBUG: Parsed user: {user}")
        print(f"📥 DEBUG: Parsed days_to_download: {days_to_download}")
        print(f"📥 DEBUG: Parsed overwrite_existing: {overwrite_existing}")
        
        # Get existing activity IDs from previous task
        existing_activity_ids = set()
        if existing_activities_check and existing_activities_check.get('status') == 'success':
            existing_activity_ids = existing_activities_check.get('existing_activity_ids', set())
            print(f"Will exclude {len(existing_activity_ids)} existing activities from download")
        else:
            print(f"No existing activities check available or failed: {existing_activities_check.get('message', 'Unknown')}")
        
        # Setup configuration directory
        default_config_dir = f'/opt/garmin/{user}'
        config_dir = get_garmin_config_dir(user, default_config_dir)

        # Initialize Garmin client with better error handling
        try:
            client = GarminClient.create_safe_client(config_dir)
        except Exception as e:
            print(f"Failed to create Garmin client: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'user': user
            }
        
        # Setup output directory
        output_directory = f"/opt/garmin/{user}"
        Path(output_directory).mkdir(parents=True, exist_ok=True)
        
        # Calculate start date: today minus days_to_download
        from datetime import date
        today = date.today()
        start_date = today - timedelta(days=days_to_download)
        
        print(f"Starting Garmin data download for user: {user}")
        print(f"Today's date: {today}")
        print(f"Start date (today - {days_to_download} days): {start_date}")
        print(f"Days to download: {days_to_download}")
        print(f"Output directory: {output_directory}")
        print(f"Overwrite existing: {overwrite_existing}")
        
        # Download data and get returned result
        try:
            download_result = client.download_daily_data(
                output_directory, 
                start_date, 
                days_to_download, 
                overwrite_existing,
                exclude_activity_ids=existing_activity_ids  # 傳入要排除的activity IDs
            )
            
            # Handle new structured return format while maintaining backward compatibility
            if isinstance(download_result, dict):
                downloaded_fit_files = download_result.get('downloaded_fit_files', [])
                file_details = download_result.get('file_details', [])
                activity_ids = download_result.get('activity_ids', [])
                download_summary = download_result.get('download_summary', {})
            else:
                # Legacy format: simple list of file paths
                downloaded_fit_files = download_result if download_result else []
                file_details = []
                activity_ids = []
                download_summary = {}
                
        except Exception as e:
            print(f"Error during download: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'user': user,
                'today_date': str(today),
                'start_date': str(start_date)
            }
        
        result = {
            'status': 'success',
            'user': user,
            'today_date': str(today),
            'start_date': str(start_date),
            'days_downloaded': days_to_download,
            'output_directory': output_directory,
            'overwrite_existing': overwrite_existing,
            'downloaded_fit_files': downloaded_fit_files,  # Maintain backward compatibility
            'total_files_found': len(downloaded_fit_files) if downloaded_fit_files else 0,
            # Enhanced metadata for processing DAG compatibility
            'file_details': file_details,
            'activity_ids': activity_ids,
            'download_summary': download_summary
        }
        result.update({
            'excluded_activities_count': len(existing_activity_ids),
            'existing_activities_check_status': existing_activities_check.get('status', 'unknown') if existing_activities_check else 'not_available'
        })
        
        print(f"Successfully downloaded {days_to_download} days of data for {user} from {start_date} to {start_date + timedelta(days=days_to_download-1)}")
        print(f"Downloaded FIT files: {len(downloaded_fit_files) if downloaded_fit_files else 0}")
        print(f"Excluded existing activities: {len(existing_activity_ids)}")
        if downloaded_fit_files:
            for fit_file in downloaded_fit_files:
                print(f"  - {fit_file}")
        
        print(f"📥 DEBUG: download_garmin_daily_data returning result: {result}")
        return result

    # Define the tasks and dependencies
    check_result = check_existing_activities()
    download_result = download_garmin_daily_data(check_result)

    # Trigger garmin_process_fit_files DAG after download completes
    trigger_processing = TriggerDagRunOperator(
        task_id='trigger_garmin_process_fit_files',
        trigger_dag_id='garmin_process_fit_files',
        conf={
            'user': '{{ params.user }}',
            'fit_file_ids': '{{ ti.xcom_pull(task_ids="download_garmin_daily_data")["activity_ids"] }}',
            'source_directory': '{{ ti.xcom_pull(task_ids="download_garmin_daily_data")["output_directory"] }}',
            'file_details': '{{ ti.xcom_pull(task_ids="download_garmin_daily_data")["file_details"] }}'
        },
        wait_for_completion=False,
        dag=dag
    )

    # Set dependencies: download_result >> trigger_processing
    download_result >> trigger_processing

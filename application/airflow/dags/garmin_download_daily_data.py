from airflow.sdk import DAG, task, Param
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
    'password': Param(
        default='example_password',
        type='string',
        title='Garmin Connect Password',
        format='password',
        description='Your Garmin Connect account password'
    ),
    'days_to_download': Param(
        default=1,
        type='integer',
        minimum=1,
        maximum=30,
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

    @task.python(task_id='download_garmin_daily_data')
    def download_garmin_daily_data(**context):
        """
        Download Garmin daily data for specified user
        
        Args:
            **context: Airflow context containing params and execution info
            
        Returns:
            dict: Status information about the download operation
        """
        # Get parameters from context
        params = context.get('params', {})
        user = params.get('user', 'example@gmail.com')
        password = params.get('password', 'example_password')
        days_to_download = params.get('days_to_download', 1)
        overwrite_existing = params.get('overwrite_existing', False)
        
        # Setup configuration directory
        default_config_dir = f'/opt/garmin/{user}'
        build_garmin_config(user, password, default_config_dir)
        config_dir = get_garmin_config_dir(user, default_config_dir)
        
        # Initialize Garmin client
        client = GarminClient(config_dir)
        
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
        
        # Download data and get returned FIT file paths
        downloaded_fit_files = client.download_daily_data(
            output_directory, 
            start_date, 
            days_to_download, 
            overwrite_existing
        )
        
        result = {
            'status': 'success',
            'user': user,
            'today_date': str(today),
            'start_date': str(start_date),
            'days_downloaded': days_to_download,
            'output_directory': output_directory,
            'overwrite_existing': overwrite_existing,
            'downloaded_fit_files': downloaded_fit_files,
            'total_files_found': len(downloaded_fit_files) if downloaded_fit_files else 0
        }
        
        print(f"Successfully downloaded {days_to_download} days of data for {user} from {start_date} to {start_date + timedelta(days=days_to_download-1)}")
        print(f"Downloaded FIT files: {len(downloaded_fit_files) if downloaded_fit_files else 0}")
        if downloaded_fit_files:
            for fit_file in downloaded_fit_files:
                print(f"  - {fit_file}")
        
        return result
        
    @task.python(task_id='analyze_garmin_fit_files')
    def analyze_garmin_fit_files(download_result, **context):
        """
        Analyze the downloaded Garmin FIT files
        
        Args:
            download_result: Result from the download task containing FIT file paths
            **context: Airflow context containing params and execution info
            
        Returns:
            dict: Analysis results for the processed FIT files
        """
        params = context.get('params', {})
        user = params.get('user', 'example@gmail.com')
        
        if not download_result or download_result.get('status') != 'success':
            print("Download task failed, skipping analysis")
            return {'status': 'skipped', 'reason': 'download_failed'}
        
        downloaded_fit_files = download_result.get('downloaded_fit_files', [])
        
        if not downloaded_fit_files:
            print("No FIT files to analyze")
            return {
                'status': 'completed',
                'user': user,
                'files_analyzed': 0,
                'analysis_results': []
            }
        
        print(f"Starting analysis of {len(downloaded_fit_files)} FIT files for user: {user}")
        
        analysis_results = []
        
        for fit_file in downloaded_fit_files:
            print(f"Analyzing FIT file: {fit_file}")
            
            # TODO: 这里你可以添加你的分析 API 调用
            # 例如:
            # analysis_api_result = your_analysis_api.analyze_fit_file(fit_file)
            
            # 暂时返回模拟的分析结果
            file_analysis = {
                'file_path': fit_file,
                'file_name': os.path.basename(fit_file),
                'analysis_timestamp': datetime.now().isoformat(),
                # TODO: 添加实际的分析结果字段
                # 'analysis_data': analysis_api_result
            }
            
            analysis_results.append(file_analysis)
            print(f"Completed analysis for: {fit_file}")
        
        result = {
            'status': 'completed',
            'user': user,
            'files_analyzed': len(analysis_results),
            'analysis_results': analysis_results,
            'total_files_processed': len(downloaded_fit_files)
        }
        
        print(f"Analysis completed for {len(analysis_results)} FIT files")
        return result


    # Define the tasks and dependencies
    download_task = download_garmin_daily_data()
    analysis_task = analyze_garmin_fit_files(download_task)
    
    # Set task dependencies
    download_task >> analysis_task

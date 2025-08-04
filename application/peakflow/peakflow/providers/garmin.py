import datetime
import json
import fitfile.conversions as conversions
import time
import os
from garmindb.download import Download
import tempfile
from garmindb.garmin_connect_config_manager import GarminConnectConfigManager
from peakflow.utils import get_logger, build_garmin_config, get_garmin_config_dir
from pathlib import Path
from typing import Optional, Set

# Universal logger for the entire module
logger = get_logger(__name__)


class CustomDownload(Download):

    def __init__(self, config: GarminConnectConfigManager):
        super().__init__(config)

    def get_activity_summaries(self, start, count):
        return self._Download__get_activity_summaries(start, count)

    def get_activity(self, activity, directory, overwite=False, sleep_time: float=0.5) -> str:
        activity_id_str = str(activity['activityId'])
        activity_name_str = conversions.printable(activity.get('activityName', 'Unknown'))
        logger.info("get_activities: %s (%s)", activity_name_str, activity_id_str)
        json_filename = f'{directory}/activity_{activity_id_str}'
        if not os.path.isfile(json_filename + '.json') or overwite:
            logger.info("get_activities: %s <- %s", json_filename, str(activity.get('activityName', 'Unknown')))
            self._Download__save_activity_details(directory, activity_id_str, overwite)
            self.save_json_to_file(json_filename, activity)
            if not os.path.isfile(f'{directory}/{activity_id_str}.fit') or overwite:
                self._Download__save_activity_file(activity_id_str)
            # pause for a second between every page access
            time.sleep(sleep_time)
        else:
            logger.info("get_activities: skipping download of %s, already present", activity_id_str)
        return activity_id_str

    def get_activities(self, directory, count, overwite=False, exclude_activity_ids: Optional[Set[str]] = None) -> list[str]:
        self.temp_dir = tempfile.mkdtemp()
        logger.info("Getting activities: directory='%s' count=%s temp=%s", directory, str(count), self.temp_dir)
        activitys = self.get_activity_summaries(0, count)
        success_activitys = []
        
        if not activitys:
            logger.warning("No activities found")
            return success_activitys
            
        for activity in activitys:
            activity_id_str = str(activity['activityId'])
            if exclude_activity_ids and activity_id_str in exclude_activity_ids:
                logger.info("Skipping activity %s (excluded)", activity_id_str)
                continue
            try:
                activity_id_str = self.get_activity(activity, directory, overwite)
                success_activitys.append(activity_id_str)
            except Exception as e:
                logger.error("Error getting activity %s: %s", str(activity.get('activityId', 'unknown')), str(e))
        
        try:
            self._Download__unzip_files(directory)
            logger.info("Unzipped files to directory: %s", directory)
        except Exception as e:
            logger.error("Error unzipping files: %s", str(e))
            
        return success_activitys


class GarminClient:

    def __init__(self, config_dir: str):
        try:
            self.config = GarminConnectConfigManager(config_dir=config_dir)
            self.downloader = CustomDownload(self.config)
            self.username = self.config.get_user()
            logger.info("Attempting to login to Garmin Connect for user: %s", self.username)
            success = self.downloader.login()
            if not success:
                raise Exception("Can't login to Garmin Connect. Please check your credentials.")
            logger.info("Successfully logged in to Garmin Connect")
        except Exception as e:
            logger.error("Failed to initialize GarminClient: %s", str(e))
            raise

    def download_activities(self, output_dir: str, start_date: datetime.date, days: int, overwrite: bool = False, exclude_activity_ids: Optional[Set[str]] = None):
        try:
            activities_path = self._ensure_directory(Path(output_dir) / "activities")
            logger.info("Downloading activity data to: %s", activities_path)
            result = self.downloader.get_activities(str(activities_path), days, overwrite, exclude_activity_ids=exclude_activity_ids)
            logger.info("Activity download completed. Downloaded %s activities", len(result) if result else 0)
            return result
        except Exception as e:
            logger.error("Error downloading activities: %s", str(e))
            raise

    def download_sleep(self, output_dir: str, start_date: datetime.date, days: int, overwrite: bool = False):
        try:
            sleep_path = self._ensure_directory(Path(output_dir) / "sleep")
            logger.info("Downloading sleep data to: %s", sleep_path)
            self.downloader.get_sleep(str(sleep_path), start_date, days, overwrite)
            logger.info("Sleep download completed")
        except Exception as e:
            logger.error("Error downloading sleep data: %s", str(e))
            raise

    def download_monitoring(self, output_dir: str, start_date: datetime.date, days: int, overwrite: bool = False):
        try:
            monitoring_path = self._ensure_directory(Path(output_dir) / "monitoring")
            logger.info("Downloading monitoring data to: %s", monitoring_path)
            self.downloader.get_monitoring(self._get_monitoring_directory_func(monitoring_path), start_date, days)
            logger.info("Monitoring download completed")
        except Exception as e:
            logger.error("Error downloading monitoring data: %s", str(e))
            raise

    def download_daily_data(self, output_dir: str, start_date: datetime.date, days: int, overwrite: bool = False, exclude_activity_ids: Optional[Set[str]] = None):
        try:
            logger.info("Starting to download %s days of daily data, starting from %s", days, start_date)
            
            # Collect all downloaded file paths and metadata
            downloaded_files = []
            downloaded_fit_files = []  # For backward compatibility
            file_details = []
            
            # Download activities and collect FIT files
            activity_results = self.download_activities(output_dir, start_date, days, overwrite, exclude_activity_ids=exclude_activity_ids)
            if activity_results:
                activities_path = Path(output_dir) / "activities"
                for activity_id in activity_results:
                    fit_file = activities_path / f"{activity_id}.fit"
                    if fit_file.exists():
                        file_path = str(fit_file)
                        downloaded_files.append(file_path)
                        downloaded_fit_files.append(file_path)  # Backward compatibility
                        
                        # Collect file metadata for processing DAG
                        file_details.append({
                            'file_path': file_path,
                            'file_name': fit_file.name,
                            'activity_id': activity_id,
                            'file_size': fit_file.stat().st_size,
                            'modified_time': fit_file.stat().st_mtime,
                            'download_date': datetime.datetime.now().isoformat()
                        })
            
            # Download other data types
            self.download_sleep(output_dir, start_date, days, overwrite)
            self.download_monitoring(output_dir, start_date, days, overwrite)
            
            # Create comprehensive result
            result = {
                'downloaded_fit_files': downloaded_fit_files,  # For backward compatibility
                'downloaded_files': downloaded_files,  # Simple list for legacy support
                'file_details': file_details,  # Detailed metadata for processing DAG
                'total_files': len(downloaded_files),
                'activity_ids': activity_results if activity_results else [],
                'excluded_count': len(exclude_activity_ids) if exclude_activity_ids else 0,
                'download_summary': {
                    'start_date': start_date.isoformat(),
                    'days': days,
                    'output_directory': output_dir,
                    'overwrite': overwrite,
                    'total_activities_downloaded': len(activity_results) if activity_results else 0,
                    'total_fit_files': len(downloaded_files),
                    'download_timestamp': datetime.datetime.now().isoformat()
                }
            }
            
            logger.info("Daily data download completed! Downloaded %s FIT files", len(downloaded_files))
            return result
            
        except Exception as e:
            logger.error("Error in download_daily_data: %s", str(e))
            raise

    def _ensure_directory(self, path: Path) -> Path:
        """
        Ensure the given directory exists. If not, create it.

        :param path: Path to the directory.
        :return: The same path after ensuring it exists.
        """
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _get_monitoring_directory_func(self, base_dir: Path):
        """
        Returns a function that provides the directory path for monitoring data by year.

        :param base_dir: Base directory for monitoring data.
        :return: A function that takes a year and returns the corresponding directory path.
        """
        def directory_func(year: int) -> Path:
            year_dir = base_dir / str(year)
            year_dir.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists
            return year_dir

        return directory_func

    @staticmethod
    def create_safe_client(config_dir: str, max_retries: int = 3):
        """
        Create a GarminClient with retry logic and better error handling.
        
        Args:
            config_dir: Configuration directory path
            max_retries: Maximum number of login attempts
            
        Returns:
            GarminClient instance
            
        Raises:
            Exception: If all login attempts fail
        """
        for attempt in range(max_retries):
            try:
                client = GarminClient(config_dir)
                return client
            except Exception as e:
                if attempt == max_retries - 1:
                    raise Exception(f"Failed to create GarminClient after {max_retries} attempts: {str(e)}")
                time.sleep(2 ** attempt)  # Exponential backoff
        return None


def main():
    """Main entry point for the peakflow-download command."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Download Garmin data using PeakFlow')
    parser.add_argument('--user', required=True, help='Garmin Connect username')
    parser.add_argument('--password', required=True, help='Garmin Connect password')
    parser.add_argument('--output-dir', required=True, help='Output directory for downloaded data')
    parser.add_argument('--config-dir', help='Configuration directory (optional)')
    parser.add_argument('--start-date', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--days', type=int, default=1, help='Number of days to download (default: 1)')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing files')
    
    args = parser.parse_args()
    
    try:
        # Parse start date
        start_date = datetime.datetime.strptime(args.start_date, '%Y-%m-%d').date()
        # Setup configuration
        config_dir = args.config_dir or f'/storage/garmin/{args.user}'
        build_garmin_config(args.user, args.password, config_dir)
        config_dir = get_garmin_config_dir(args.user, config_dir)
        # Create client and download data
        client = GarminClient(config_dir)
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        client.download_daily_data(args.output_dir, start_date, args.days, args.overwrite)
        print(f"Successfully downloaded {args.days} days of data starting from {start_date}")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

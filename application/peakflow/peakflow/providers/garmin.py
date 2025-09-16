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

    def get_activities(self, directory, count, overwite=False, exclude_activity_ids: Optional[Set[str]] = None):
        self.temp_dir = tempfile.mkdtemp()
        logger.info("Getting activities: directory='%s' count=%s temp=%s", directory, str(count), self.temp_dir)
        activitys = self.get_activity_summaries(0, count)
        
        if not activitys:
            logger.warning("No activities found")
            # Don't use return in a generator - yield nothing and let the generator complete naturally
        else:
            for activity in activitys:
                activity_id_str = str(activity['activityId'])
                if exclude_activity_ids and activity_id_str in exclude_activity_ids:
                    logger.info("Skipping activity %s (excluded)", activity_id_str)
                    continue
                try:
                    activity_id_str = self.get_activity(activity, directory, overwite)
                    
                    # Immediately unzip the individual activity to ensure FIT file exists
                    try:
                        # Try to unzip just this activity's files
                        self._Download__unzip_files(directory)
                        logger.info("Unzipped activity %s files", activity_id_str)
                    except Exception as unzip_error:
                        logger.warning("Error unzipping activity %s: %s", activity_id_str, str(unzip_error))
                    
                    yield activity_id_str
                except Exception as e:
                    logger.error("Error getting activity %s: %s", str(activity.get('activityId', 'unknown')), str(e))
                    # Continue with next activity instead of stopping iteration
        
        # Final unzip operation to catch any remaining files (redundant but safe)
        try:
            self._Download__unzip_files(directory)
            logger.info("Final unzip completed for directory: %s", directory)
        except Exception as e:
            logger.error("Error in final unzip operation: %s", str(e))


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
            yield from self.downloader.get_activities(str(activities_path), days, overwrite, exclude_activity_ids=exclude_activity_ids)
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
        """
        Iterator version: yields metadata for each FIT file as soon as it is downloaded and available.
        """
        try:
            # Use user_id override for output directory if available
            if hasattr(self, '_user_id_override') and self._user_id_override:
                user_output_dir = Path(output_dir) / self._user_id_override
                user_output_dir.mkdir(parents=True, exist_ok=True)
                logger.info("Using user_id override directory: %s", user_output_dir)
                output_dir = str(user_output_dir)
            
            logger.info("Starting to download %s days of daily data, starting from %s", days, start_date)
            activities_path = self._ensure_directory(Path(output_dir) / "activities")
            print(output_dir, start_date, days, overwrite, exclude_activity_ids)
            # Track yielded activities to avoid duplicates
            yielded_activities = set()
            
            # download_activities is a generator, so we iterate over its results
            for activity_id in self.download_activities(output_dir, start_date, days, overwrite, exclude_activity_ids=exclude_activity_ids):
                if activity_id in yielded_activities:
                    continue
                    
                # Check for multiple possible FIT file naming patterns
                possible_fit_files = [
                    activities_path / f"{activity_id}.fit",           # Standard pattern
                    activities_path / f"{activity_id}_ACTIVITY.fit",  # Garmin's actual pattern
                    activities_path / f"activity_{activity_id}.fit"   # Alternative pattern
                ]
                
                # Find the actual FIT file that exists
                actual_fit_file = None
                for fit_file_candidate in possible_fit_files:
                    if fit_file_candidate.exists() and fit_file_candidate.stat().st_size > 0:
                        actual_fit_file = fit_file_candidate
                        break
                
                # Wait a bit and check if FIT file exists, with retry logic
                max_retries = 5
                retry_delay = 0.5
                
                for attempt in range(max_retries):
                    # Re-check for files in case unzip completed during retry
                    if actual_fit_file is None:
                        for fit_file_candidate in possible_fit_files:
                            if fit_file_candidate.exists() and fit_file_candidate.stat().st_size > 0:
                                actual_fit_file = fit_file_candidate
                                break
                    
                    if actual_fit_file is not None:
                        file_path = str(actual_fit_file)
                        metadata = {
                            'file_path': file_path,
                            'file_name': actual_fit_file.name,
                            'activity_id': activity_id,
                            'file_size': actual_fit_file.stat().st_size,
                            'modified_time': actual_fit_file.stat().st_mtime,
                            'download_date': datetime.datetime.now().isoformat(),
                            'output_directory': str(activities_path)
                        }
                        logger.info(f"Yielding downloaded FIT file: {file_path}")
                        yielded_activities.add(activity_id)
                        yield metadata
                        break
                    else:
                        if attempt < max_retries - 1:
                            logger.debug(f"FIT file not ready for {activity_id}, attempt {attempt + 1}/{max_retries}")
                            time.sleep(retry_delay)
                        else:
                            # FIT file not found after all retries - this is a serious issue
                            logger.error(f"CRITICAL: No FIT file found for activity {activity_id} after {max_retries} attempts")
                            logger.error(f"Checked patterns: {[str(f) for f in possible_fit_files]}")
                            logger.error(f"Activity {activity_id} will be skipped - potential data loss!")
                            
                            # Check if any files exist for this activity to help debug
                            activity_files = list(activities_path.glob(f"*{activity_id}*"))
                            if activity_files:
                                logger.info(f"Found related files for activity {activity_id}: {[f.name for f in activity_files]}")
                            else:
                                logger.error(f"No files found for activity {activity_id} in {activities_path}")
                            
                            # Yield error metadata instead of silently dropping the activity
                            error_metadata = {
                                'file_path': str(possible_fit_files[0]),  # Expected path
                                'file_name': possible_fit_files[0].name,
                                'activity_id': activity_id,
                                'file_size': 0,
                                'modified_time': 0,
                                'download_date': datetime.datetime.now().isoformat(),
                                'output_directory': str(activities_path),
                                'error': f'FIT file not found after {max_retries} attempts',
                                'status': 'error'
                            }
                            yielded_activities.add(activity_id)
                            yield error_metadata

            # Download other data types (sleep, monitoring) after activities
            self.download_sleep(output_dir, start_date, days, overwrite)
            self.download_monitoring(output_dir, start_date, days, overwrite)
        except Exception as e:
            logger.error("Error in download_daily_data (iterator): %s", str(e))
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

    @classmethod
    def create_from_config(cls, config_dict: dict, user_id: str = None, config_base_dir: str = None) -> 'GarminClient':
        """Create GarminClient from in-memory config dictionary."""
        from ..const import DEFAULT_GARMIN_CONFIG_DIR
        from ..utils import get_garmin_config_dir
        
        if user_id:
            # Use the standard Garmin config directory structure
            if config_base_dir:
                # If config_base_dir is provided, user_id folder should be created directly under it
                config_dir = str(Path(config_base_dir) / user_id)
                Path(config_dir).mkdir(parents=True, exist_ok=True)
            else:
                # Use DEFAULT_GARMIN_CONFIG_DIR format with {user} placeholder
                base_dir = DEFAULT_GARMIN_CONFIG_DIR
                config_dir = get_garmin_config_dir(user_id, base_dir)
        else:
            # Fallback to temporary directory for backward compatibility
            config_dir = tempfile.mkdtemp()
        
        config_file = Path(config_dir) / "GarminConnectConfig.json"
        
        try:
            # If config_dict is just credentials, expand it to full config structure
            if 'credentials' not in config_dict and ('user' in config_dict or 'password' in config_dict):
                # This is a simple credentials dict, expand it to full config
                from ..const import DEFAULT_GARMIN_CONFIG
                full_config = DEFAULT_GARMIN_CONFIG.copy()
                full_config['credentials']['user'] = config_dict.get('user', '')
                full_config['credentials']['password'] = config_dict.get('password', '')
                config_to_write = full_config
            else:
                # This is already a full config
                config_to_write = config_dict
            
            # Write config to directory (creates directory if needed)
            with open(config_file, 'w') as f:
                json.dump(config_to_write, f, indent=4)
            
            # Create client using config directory
            client = cls(config_dir)
            
            # Override the username used for directory creation with user_id
            if user_id:
                client._user_id_override = user_id
            
            # Store config_dir for reference (no cleanup needed for permanent dirs)
            client._config_dir = config_dir
            client._is_temp_config = user_id is None  # Only temp if no user_id provided
            
            return client
        except Exception as e:
            # Only clean up if it was a temporary directory
            if user_id is None:
                import shutil
                shutil.rmtree(config_dir, ignore_errors=True)
            logger.error(f"Failed to create GarminClient from config: {e}")
            raise

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
    parser.add_argument('--user-id', required=True, help='User ID for file organization')
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
        config_dir = args.config_dir or f'/storage/garmin/{args.user_id}'
        build_garmin_config(args.user_id, args.user, args.password, config_dir)
        config_dir = get_garmin_config_dir(args.user_id, config_dir)
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

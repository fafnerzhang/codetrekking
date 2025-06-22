import datetime
import json
import fitfile.conversions as conversions
import time
import os
from garmindb.download import Download, root_logger, logger
import tempfile
from garmindb.garmin_connect_config_manager import GarminConnectConfigManager
from peakflow.utils import get_logger, build_garmin_config, get_garmin_config_dir
from pathlib import Path
from typing import Optional, Set


class CustomDownload(Download):

    def __init__(self, config: GarminConnectConfigManager):
        super().__init__(config)

    def get_activity_summaries(self, start, count):
        return self._Download__get_activity_summaries(start, count)

    def get_activity(self, activity, directory, overwite=False, sleep_time: float=0.5):
        activity_id_str = str(activity['activityId'])
        activity_name_str = conversions.printable(activity.get('activityName'))
        root_logger.info("get_activities: %s (%s)", activity_name_str, activity_id_str)
        json_filename = f'{directory}/activity_{activity_id_str}'
        if not os.path.isfile(json_filename + '.json') or overwite:
            root_logger.info("get_activities: %s <- %r", json_filename, activity)
            self.__save_activity_details(directory, activity_id_str, overwite)
            self.save_json_to_file(json_filename, activity)
            if not os.path.isfile(f'{directory}/{activity_id_str}.fit') or overwite:
                self.__save_activity_file(activity_id_str)
            # pause for a second between every page access
            time.sleep(sleep_time)
        else:
            root_logger.info("get_activities: skipping download of %s, already present", activity_id_str)
        return activity_id_str

    def get_activities(self, directory, count, overwite=False, exclude_activity_ids: Optional[Set[str]] = None):
        self.temp_dir = tempfile.mkdtemp()
        logger.info("Getting activities: '%s' (%d) temp %s", directory, self.temp_dir)
        activitys = self.get_activity_summaries(0, count)
        success_activitys = []
        for activity in activitys:
            activity_id_str = str(activity['activityId'])
            if exclude_activity_ids and activity_id_str in exclude_activity_ids:
                logger.info(f"Skipping activity {activity_id_str} (excluded)")
                continue
            try:
                activity_id_str = self.get_activity(activity, directory, count, overwite)
                success_activitys.append(activity_id_str)
            except Exception as e:
                logger.error("Error getting activity %s: %s", activity, e)
        return success_activitys


class GarminClient:

    logger = get_logger(__name__)
    
    def __init__(self, config_dir: str):
        self.config = GarminConnectConfigManager(config_dir=config_dir)
        self.downloader = CustomDownload(self.config)
        self.username = self.config.get_user()
        success = self.downloader.login()
        if not success:
            raise Exception("Can't login to Garmin Connect. Please check your credentials.")

    def download_activities(self, output_dir: str, start_date: datetime.date, days: int, overwrite: bool = False, exclude_activity_ids: Optional[Set[str]] = None):
        activities_path = self._ensure_directory(Path(output_dir) / "activities")
        logger.info("Downloading activity data...")
        self.downloader.get_activities(str(activities_path), days, overwrite, exclude_activity_ids=exclude_activity_ids)

    def download_sleep(self, output_dir: str, start_date: datetime.date, days: int, overwrite: bool = False):
        sleep_path = self._ensure_directory(Path(output_dir) / "sleep")
        logger.info("Downloading sleep data...")
        self.downloader.get_sleep(str(sleep_path), start_date, days, overwrite)

    def download_monitoring(self, output_dir: str, start_date: datetime.date, days: int, overwrite: bool = False):
        monitoring_path = self._ensure_directory(Path(output_dir) / "monitoring")
        logger.info("Downloading monitoring data...")
        self.downloader.get_monitoring(self._get_monitoring_directory_func(monitoring_path), start_date, days)

    def download_daily_data(self, output_dir: str, start_date: datetime.date, days: int, overwrite: bool = False):
        logger.info(f"Starting to download {days} days of daily data, starting from {start_date}...")
        self.download_activities(output_dir, start_date, days, overwrite)
        self.download_sleep(output_dir, start_date, days, overwrite)
        self.download_monitoring(output_dir, start_date, days, overwrite)
        logger.info("Daily data download completed!")

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
        config_dir = args.config_dir or f'/tmp/garmin_config/{args.user}'
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

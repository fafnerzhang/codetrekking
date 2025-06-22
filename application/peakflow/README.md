# PeakFlow

A comprehensive fitness data pipeline for Garmin activity extraction, analysis, and visualization.

## Overview

PeakFlow provides a complete solution for fitness enthusiasts and data analysts:
- **Data Extraction**: Seamlessly pull activity data from Garmin Connect
- **Automated Processing**: Transform and analyze fitness data using Airflow workflows
- **Advanced Analytics**: Store and visualize data in Elasticsearch for deep insights
- **Performance Tracking**: Monitor your fitness journey with powerful analytics

## Features

- 🏃‍♂️ **Garmin Integration**: Connect directly to your Garmin devices and Garmin Connect
- 🔄 **Automated Workflows**: Schedule and automate data processing with Airflow
- 📊 **Elasticsearch Storage**: Scalable data storage with advanced search capabilities  
- 🧹 **Data Processing**: Clean, transform, and enrich your fitness data
- 📈 **Visualization Ready**: Prepared data for Kibana dashboards and custom analytics
- ⚡ **Real-time Sync**: Keep your data up-to-date automatically

## Installation

### From source

```bash
pip install -e .
```

### Development installation

```bash
pip install -e ".[dev]"
```

## Usage

### Basic Usage

```python
from garmin.client import GarminClient
from garmin.utils import build_config, get_config_dir
from garmin.const import DEFAULT_CONFIG_DIR
import datetime

# Setup configuration
user = 'your-email@example.com'
password = 'your-password'
build_config(user, password, DEFAULT_CONFIG_DIR)
config_dir = get_config_dir(user, DEFAULT_CONFIG_DIR)

# Initialize client
client = GarminClient(config_dir)

# Download data
output_directory = "/path/to/output"
start_date = datetime.date(2024, 1, 1)
days_to_download = 30
client.download_daily_data(output_directory, start_date, days_to_download)
```

### Download Activities Only

```python
# Get activity summaries
activities = client.downloader.get_activity_summaries(0, 10)
for activity in activities:
    print(f"Activity: {activity['activityName']} - {activity['activityId']}")
```

## Configuration

The toolkit uses a configuration system that allows you to customize:

- Database settings
- Garmin domain and credentials
- Data date ranges
- Directory structures
- Enabled statistics tracking

## Requirements

- Python 3.8+
- garmindb
- garth
- fitfile

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black .
```

### Type Checking

```bash
mypy .
```

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Changelog

### 0.1.0
- Initial release
- Basic Garmin data downloading functionality
- Configuration management
- Activity, sleep, and monitoring data support

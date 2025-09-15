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
- 🎯 **Power Zone Calculator**: Advanced power zone analysis for running and cycling
- 💓 **Heart Rate Analytics**: Comprehensive heart rate zone calculations
- 🏃 **Pace Zone Analysis**: Multiple pace zone methodologies for training
- 📊 **Training Analytics**: TSS, fitness metrics, and performance tracking

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

## Analytics

PeakFlow includes comprehensive analytics capabilities for detailed training analysis:

### Power Zone Calculator

Calculate training zones based on multiple established methodologies:

```python
from peakflow.analytics import PowerZoneAnalyzer, PowerZoneMethod

analyzer = PowerZoneAnalyzer()

# Steve Palladino running power zones
result = analyzer.calculate_power_zones(
    threshold_power=200.0,  # FTP in watts
    method=PowerZoneMethod.STEVE_PALLADINO,
    body_weight=70.0  # kg (optional)
)

# Access calculated zones
for zone in result.zones:
    print(f"Zone {zone.zone_number}: {zone.zone_name}")
    print(f"Power Range: {zone.power_range[0]:.0f}-{zone.power_range[1]:.0f}W")
    print(f"Purpose: {zone.purpose}")
```

**Supported Methods:**
- **Steve Palladino** (7 zones) - Running power zones based on FTP/CP
- **Stryd Running** (7 zones) - Stryd-specific running power zones
- **Cycling FTP** (7 zones) - Traditional cycling power zones
- **Critical Power** (7 zones) - CP model with W' capacity

### Heart Rate & Pace Zones

```python
from peakflow.analytics import HeartRateZoneAnalyzer, PaceZoneAnalyzer

# Heart rate zones
hr_analyzer = HeartRateZoneAnalyzer()
hr_result = hr_analyzer.calculate_zones(max_hr=190, method="bcf_abcc_wcpp_revised")

# Pace zones  
pace_analyzer = PaceZoneAnalyzer()
pace_result = pace_analyzer.calculate_zones(threshold_pace=240, method="jack_daniels")
```

See the complete documentation:
- [Power Zones README](POWER_ZONES_README.md)
- [Pace Zones README](PACE_ZONES_README.md)

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

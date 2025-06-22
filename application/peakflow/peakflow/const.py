import pathlib


USER_HOME = pathlib.Path.home()
DEFAULT_GARMIN_CONFIG_DIR = USER_HOME / 'storage' / 'garmin' / '{user}'
DEFAULT_GARMIN_CONFIG = {
    "db": {
        "type"                          : "sqlite"
    },
    "garmin": {
        "domain"                        : "garmin.com"
    },
    "credentials": {
        "user"                          : "",
        "secure_password"               : False,
        "password"                      : "",
        "password_file"                 : None
    },
    "data": {
        "weight_start_date"             : "12/31/2019",
        "sleep_start_date"              : "12/31/2019",
        "rhr_start_date"                : "12/31/2019",
        "monitoring_start_date"         : "12/31/2019",
        "download_latest_activities"    : 25,
        "download_all_activities"       : 1000
    },
    "directories": {
        "relative_to_home"              : True,
        "base_dir"                      : "HealthData",
        "mount_dir"                     : "/Volumes/GARMIN"
    },
    "enabled_stats": {
        "monitoring"                    : True,
        "steps"                         : True,
        "itime"                         : True,
        "sleep"                         : True,
        "rhr"                           : True,
        "weight"                        : True,
        "activities"                    : True
    },
    "course_views": {
        "steps"                         : []
    },
    "modes": {
    },
    "activities": {
        "display"                       : []
    },
    "settings": {
        "metric"                        : False,
        "default_display_activities"    : ["walking", "running", "cycling"]
    },
    "checkup": {
        "look_back_days"                : 90
    }
}
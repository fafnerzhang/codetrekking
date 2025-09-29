#!/usr/bin/env python3
"""
Training Stress Score (TSS) Algorithm Implementation

Training Stress Score (TSS) is a composite number that takes into account the duration 
and intensity of a workout to arrive at a single estimate of the overall training load 
and physiological stress created by that training session.

TSS can be calculated using different metrics:
1. Power-based TSS: Uses Normalized Power (NP) and Functional Threshold Power (FTP)
2. Heart Rate-based TSS (hrTSS): Uses heart rate zones and thresholds
3. Pace-based TSS: Uses pace zones and thresholds for running

Formulas:
- Power TSS = (seconds × NP × IF) / (FTP × 3600) × 100
- HR TSS = (Duration in hours × IF²) × 100
- Running Pace TSS = (Duration in hours × IF²) × 100

Where IF (Intensity Factor) represents the ratio of effort to threshold
"""

from typing import Dict, List, Any, Optional, Tuple, Literal
from datetime import datetime, timedelta
import numpy as np
from statistics import mean
from math import sqrt
from pydantic import BaseModel, Field, field_validator

from ..storage.interface import (
    StorageInterface, DataType, QueryFilter, AggregationQuery
)
from .interface import (
    AnalyticsFilter, AnalyticsResult, AnalyticsType, MetricThresholds,
    InsufficientDataError, CalculationError
)
from ..utils import get_logger


logger = get_logger(__name__)


class WorkoutPlanSegment(BaseModel):
    """
    Represents a segment of a workout plan with specific intensity and duration.

    This is the core data structure for workout plan TSS estimation.
    Simple, no special cases - just intensity and time.
    """
    duration_minutes: float = Field(..., gt=0, description="Duration in minutes (must be positive)")
    intensity_metric: Literal['power', 'heart_rate', 'pace'] = Field(..., description="Type of intensity metric")
    target_value: float = Field(..., gt=0, description="Target intensity value (watts, bpm, or min/km)")

    @field_validator('target_value')
    @classmethod
    def validate_target_value(cls, v, info):
        """Validate target value based on intensity metric"""
        if info.data:
            intensity_metric = info.data.get('intensity_metric')

            if intensity_metric == 'power' and v > 2000:
                raise ValueError("Power target seems unreasonably high (>2000W)")
            elif intensity_metric == 'heart_rate' and (v < 30 or v > 250):
                raise ValueError("Heart rate target should be between 30-250 bpm")
            elif intensity_metric == 'pace' and (v < 1.0 or v > 20.0):
                raise ValueError("Pace target should be between 1:00-20:00 min/km")

        return v

    def duration_hours(self) -> float:
        """Convert duration to hours for TSS calculations"""
        return self.duration_minutes / 60.0


class WorkoutPlan(BaseModel):
    """
    Represents a complete workout plan as a collection of segments.

    Linus principle: Eliminate special cases by treating everything as segments.
    No warm-up, cool-down, or interval special handling - just segments.
    """
    segments: List[WorkoutPlanSegment] = Field(..., min_length=1, description="Workout segments")
    name: Optional[str] = Field(None, description="Optional workout name")
    description: Optional[str] = Field(None, description="Optional workout description")

    def total_duration_minutes(self) -> float:
        """Calculate total workout duration"""
        return sum(segment.duration_minutes for segment in self.segments)

    def total_duration_hours(self) -> float:
        """Calculate total workout duration in hours"""
        return self.total_duration_minutes() / 60.0


class TSSCalculator:
    """Training Stress Score calculator class"""
    
    def __init__(self, storage: StorageInterface, thresholds: Optional[MetricThresholds] = None):
        self.storage = storage
        self.thresholds = thresholds or MetricThresholds()
    
    @staticmethod
    def speed_to_pace_per_km(speed_ms: float) -> float:
        """
        Convert speed in m/s to pace in minutes per kilometer
        
        Args:
            speed_ms: Speed in meters per second
            
        Returns:
            Pace in minutes per kilometer
        """
        if speed_ms <= 0:
            return float('inf')
        
        # Convert m/s to km/h, then to min/km
        # 1 m/s = 3.6 km/h
        # pace (min/km) = 60 / speed (km/h)
        speed_kmh = speed_ms * 3.6
        pace_min_per_km = 60.0 / speed_kmh
        return pace_min_per_km
    
    @staticmethod
    def pace_per_km_to_speed(pace_min_per_km: float) -> float:
        """
        Convert pace in minutes per kilometer to speed in m/s
        
        Args:
            pace_min_per_km: Pace in minutes per kilometer
            
        Returns:
            Speed in meters per second
        """
        if pace_min_per_km <= 0:
            return 0.0
        
        # Convert min/km to km/h, then to m/s
        speed_kmh = 60.0 / pace_min_per_km
        speed_ms = speed_kmh / 3.6
        return speed_ms
    
    @staticmethod
    def format_pace(pace_min_per_km: float) -> str:
        """
        Format pace as MM:SS per km
        
        Args:
            pace_min_per_km: Pace in minutes per kilometer
            
        Returns:
            Formatted pace string (e.g., "4:30")
        """
        if pace_min_per_km == float('inf'):
            return "∞:∞"
        
        minutes = int(pace_min_per_km)
        seconds = int((pace_min_per_km - minutes) * 60)
        return f"{minutes}:{seconds:02d}"
    
    @staticmethod
    def parse_pace(pace_str: str) -> float:
        """
        Parse pace string (MM:SS) to minutes per kilometer
        
        Args:
            pace_str: Pace string in format "MM:SS" (e.g., "4:30")
            
        Returns:
            Pace in minutes per kilometer
        """
        try:
            if ':' not in pace_str:
                return float(pace_str)  # Assume it's already in decimal minutes
            
            parts = pace_str.split(':')
            minutes = int(parts[0])
            seconds = int(parts[1])
            return minutes + (seconds / 60.0)
        except (ValueError, IndexError):
            raise ValueError(f"Invalid pace format: {pace_str}. Expected MM:SS or decimal minutes.")
    
    def calculate_power_tss(self, activity_id: str = None, ftp: Optional[float] = None, threshold_power: Optional[float] = None, raw_data: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Calculate Power-based Training Stress Score

        Args:
            activity_id: Activity identifier (used if raw_data is None)
            ftp: Functional Threshold Power for cycling (watts). If None, will attempt to estimate from data
            threshold_power: Threshold Power for running (watts). Takes precedence over ftp if provided
            raw_data: Optional list of record dictionaries containing power data

        Returns:
            Dictionary containing TSS calculation results
        """
        try:
            # Get power data for the activity
            power_data = self._get_power_data(activity_id, raw_data=raw_data)
            
            if not power_data:
                raise InsufficientDataError("No power data available for TSS calculation")
            
            # Use provided Threshold Power (running) or FTP (cycling) or estimate from thresholds
            final_threshold_power = threshold_power or ftp
            if final_threshold_power is None:
                final_threshold_power = self._estimate_ftp(activity_id or "raw_data")
                if final_threshold_power is None:
                    raise CalculationError("Threshold power/FTP not provided and cannot be estimated")
            
            # Calculate Normalized Power (NP)
            normalized_power = self._calculate_normalized_power(power_data)
            
            # Calculate duration in seconds
            duration_seconds = len(power_data)
            
            # Calculate Intensity Factor (IF)
            intensity_factor = normalized_power / final_threshold_power if final_threshold_power > 0 else 0

            # Calculate TSS
            tss = (duration_seconds * normalized_power * intensity_factor) / (final_threshold_power * 3600) * 100

            return {
                "tss": round(tss, 1),
                "normalized_power": round(normalized_power, 1),
                "intensity_factor": round(intensity_factor, 3),
                "ftp": ftp,  # Keep for backward compatibility
                "threshold_power": final_threshold_power,  # The actual value used
                "duration_seconds": duration_seconds,
                "duration_hours": round(duration_seconds / 3600, 2),
                "avg_power": round(mean(power_data), 1),
                "max_power": max(power_data),
                "calculation_method": "power"
            }
            
        except Exception as e:
            activity_ref = activity_id or "raw_data"
            logger.error(f"Error calculating power TSS for activity {activity_ref}: {str(e)}")
            raise CalculationError(f"Power TSS calculation failed: {str(e)}")
    
    def calculate_hr_tss(self, activity_id: str = None, threshold_hr: Optional[int] = None, 
                        max_hr: Optional[int] = None, raw_data: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Calculate Heart Rate-based Training Stress Score
        
        Args:
            activity_id: Activity identifier (used if raw_data is None)
            threshold_hr: Lactate threshold heart rate (LTHR)
            max_hr: Maximum heart rate
            raw_data: Optional list of record dictionaries containing heart rate data
            
        Returns:
            Dictionary containing hrTSS calculation results
        """
        try:
            # Get heart rate data for the activity
            hr_data = self._get_heart_rate_data(activity_id, raw_data=raw_data)
            
            if not hr_data:
                raise InsufficientDataError("No heart rate data available for hrTSS calculation")
            
            # Use provided threshold HR or estimate from zones
            if threshold_hr is None:
                threshold_hr = self._estimate_threshold_hr()
                if threshold_hr is None:
                    raise CalculationError("Threshold HR not provided and cannot be estimated")
            
            if max_hr is None:
                max_hr = self._estimate_max_hr(hr_data)
            
            # Calculate duration in hours
            duration_hours = len(hr_data) / 3600
            
            # Calculate average heart rate
            avg_hr = mean(hr_data)
            
            # Calculate Intensity Factor using TRIMP method
            intensity_factor = self._calculate_hr_intensity_factor(hr_data, threshold_hr, max_hr)
            
            # Calculate hrTSS
            hr_tss = duration_hours * (intensity_factor ** 2) * 100
            
            return {
                "tss": round(hr_tss, 1),
                "intensity_factor": round(intensity_factor, 3),
                "threshold_hr": threshold_hr,
                "max_hr": max_hr,
                "avg_hr": round(avg_hr, 1),
                "duration_hours": round(duration_hours, 2),
                "duration_seconds": len(hr_data),
                "calculation_method": "heart_rate"
            }
            
        except Exception as e:
            activity_ref = activity_id or "raw_data"
            logger.error(f"Error calculating hrTSS for activity {activity_ref}: {str(e)}")
            raise CalculationError(f"hrTSS calculation failed: {str(e)}")
    
    def calculate_running_pace_tss(self, activity_id: str = None, threshold_pace: Optional[float] = None, raw_data: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Calculate Running Pace-based Training Stress Score (rTSS)
        
        Running TSS uses pace zones and normalized graded pace.
        The intensity factor is calculated as: threshold_pace / normalized_pace 
        (where lower pace values indicate faster/harder effort)
        
        Formula: rTSS = (Duration in hours) * (IF^2) * 100
        This follows the same approach as heart rate TSS
        
        Args:
            activity_id: Activity identifier (used if raw_data is None)
            threshold_pace: Functional threshold pace in minutes per kilometer
            raw_data: Optional list of record dictionaries containing speed data
            
        Returns:
            Dictionary containing running pace TSS calculation results
        """
        try:
            # Get speed data for the activity and convert to pace
            speed_data = self._get_speed_data(activity_id, raw_data=raw_data)
            
            if not speed_data:
                raise InsufficientDataError("No speed data available for running pace TSS calculation")
            
            # Convert speed (m/s) to pace (min/km)
            pace_data = [self.speed_to_pace_per_km(speed) for speed in speed_data if speed > 0]
            
            if not pace_data:
                raise InsufficientDataError("No valid pace data available for running pace TSS calculation")
            
            # Use provided threshold pace or estimate
            if threshold_pace is None:
                threshold_pace = self._estimate_threshold_pace(activity_id or "raw_data")
                if threshold_pace is None:
                    raise CalculationError("Threshold pace not provided and cannot be estimated")
            
            # Calculate duration in hours
            duration_hours = len(pace_data) / 3600
            
            # Calculate Normalized Graded Pace (NGP) for running
            normalized_pace = self._calculate_normalized_pace(pace_data)
            
            # Calculate Intensity Factor for running (corrected formula)
            # IF = threshold_pace / normalized_pace 
            # For pace: faster pace (lower number) = higher intensity
            # So IF should be greater than 1.0 when running faster than threshold pace
            intensity_factor = threshold_pace / normalized_pace if normalized_pace > 0 else 0
            
            # Cap intensity factor at reasonable bounds (0.0 to 2.0)
            intensity_factor = max(0.0, min(intensity_factor, 2.0))
            
            # Calculate running pace TSS (rTSS)
            # For pace-based TSS, we use the standard TSS formula adapted for running:
            # rTSS = (Duration in hours) * (IF^2) * 100
            # This is the same approach used for heart rate TSS
            duration_seconds = len(pace_data)
            duration_hours = duration_seconds / 3600
            running_tss = duration_hours * (intensity_factor ** 2) * 100
            
            avg_pace = mean(pace_data)
            best_pace = min(pace_data)  # Fastest pace (lowest time)
            
            return {
                "tss": round(running_tss, 1),
                "normalized_pace": round(normalized_pace, 2),
                "normalized_pace_formatted": self.format_pace(normalized_pace),
                "intensity_factor": round(intensity_factor, 3),
                "threshold_pace": threshold_pace,
                "threshold_pace_formatted": self.format_pace(threshold_pace),
                "avg_pace": round(avg_pace, 2),
                "avg_pace_formatted": self.format_pace(avg_pace),
                "best_pace": round(best_pace, 2),
                "best_pace_formatted": self.format_pace(best_pace),
                "duration_hours": round(duration_hours, 2),
                "duration_seconds": len(pace_data),
                "calculation_method": "pace"
            }
            
        except Exception as e:
            activity_ref = activity_id or "raw_data"
            logger.error(f"Error calculating running pace TSS for activity {activity_ref}: {str(e)}")
            raise CalculationError(f"Running pace TSS calculation failed: {str(e)}")
    
    def calculate_pace_tss(self, activity_id: str = None, threshold_pace: Optional[float] = None, raw_data: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Backward compatibility method for calculate_running_pace_tss

        Args:
            activity_id: Activity identifier (used if raw_data is None)
            threshold_pace: Functional threshold pace in minutes per kilometer
            raw_data: Optional list of record dictionaries containing speed data

        Returns:
            Dictionary containing running pace TSS calculation results
        """
        return self.calculate_running_pace_tss(activity_id, threshold_pace, raw_data)

    def estimate_workout_plan_tss(self, workout_plan: WorkoutPlan,
                                 ftp: Optional[float] = None,
                                 threshold_power: Optional[float] = None,
                                 threshold_hr: Optional[int] = None,
                                 max_hr: Optional[int] = None,
                                 threshold_pace: Optional[float] = None,
                                 user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Estimate TSS for a planned workout before execution.

        Linus principle: Dumbest possible implementation - just simulate the data
        and use existing TSS calculation logic. No special cases.

        Args:
            workout_plan: WorkoutPlan containing segments with target intensities
            ftp: Functional Threshold Power (watts)
            threshold_hr: Lactate threshold heart rate
            max_hr: Maximum heart rate
            threshold_pace: Functional threshold pace (min/km)
            user_id: User identifier (used to retrieve stored thresholds)

        Returns:
            Dictionary containing estimated TSS and segment breakdown
        """
        if not workout_plan.segments:
            raise InsufficientDataError("Workout plan must contain at least one segment")

        try:
            # Get user thresholds if user_id is provided (same as composite TSS)
            user_thresholds = {}
            if user_id:
                user_thresholds = self._get_user_thresholds(user_id)
                logger.debug(f"Retrieved user thresholds for {user_id}: {list(user_thresholds.keys())}")

            # Merge user thresholds with provided parameters (parameters take precedence)
            ftp = ftp or user_thresholds.get('ftp')
            threshold_power = threshold_power or user_thresholds.get('threshold_power')
            threshold_hr = threshold_hr or user_thresholds.get('threshold_hr')
            max_hr = max_hr or user_thresholds.get('max_hr')
            threshold_pace = threshold_pace or user_thresholds.get('threshold_pace')

            # Group segments by intensity metric type
            power_segments = [s for s in workout_plan.segments if s.intensity_metric == 'power']
            hr_segments = [s for s in workout_plan.segments if s.intensity_metric == 'heart_rate']
            pace_segments = [s for s in workout_plan.segments if s.intensity_metric == 'pace']

            segment_estimates = []
            total_estimated_tss = 0.0

            # Calculate TSS for each segment type using existing logic
            # Also capture estimated thresholds from the internal calculations
            if power_segments:
                # Use threshold_power if provided, otherwise ftp, otherwise estimate
                final_threshold_power = threshold_power or ftp
                if final_threshold_power is None:
                    final_threshold_power = self._estimate_ftp("workout_plan")
                power_tss_data = self._estimate_power_segments_tss(power_segments, final_threshold_power)
                # Update the variables for return values - use threshold_power terminology
                threshold_power = final_threshold_power
                if not ftp:  # Only set ftp for backward compatibility if not already set
                    ftp = final_threshold_power
                segment_estimates.extend(power_tss_data['segments'])
                total_estimated_tss += power_tss_data['total_tss']

            if hr_segments:
                if threshold_hr is None:
                    threshold_hr = self._estimate_threshold_hr()
                if max_hr is None:
                    max_hr = self._estimate_max_hr([])
                hr_tss_data = self._estimate_hr_segments_tss(hr_segments, threshold_hr, max_hr)
                segment_estimates.extend(hr_tss_data['segments'])
                total_estimated_tss += hr_tss_data['total_tss']

            if pace_segments:
                if threshold_pace is None:
                    threshold_pace = self._estimate_threshold_pace("workout_plan")
                pace_tss_data = self._estimate_pace_segments_tss(pace_segments, threshold_pace)
                segment_estimates.extend(pace_tss_data['segments'])
                total_estimated_tss += pace_tss_data['total_tss']

            if not segment_estimates:
                raise InsufficientDataError("No valid segments found in workout plan")

            # Determine primary method based on segment count
            primary_method = self._determine_primary_method(power_segments, hr_segments, pace_segments)

            return {
                'estimated_tss': round(total_estimated_tss, 1),
                'total_duration_minutes': workout_plan.total_duration_minutes(),
                'total_duration_hours': workout_plan.total_duration_hours(),
                'segment_count': len(workout_plan.segments),
                'primary_method': primary_method,
                'segments': segment_estimates,
                'thresholds_used': {
                    'ftp': ftp,
                    'threshold_power': threshold_power,  # The actual power value used
                    'threshold_hr': threshold_hr,
                    'max_hr': max_hr,
                    'threshold_pace': threshold_pace,
                    'source': 'user_indicators' if user_thresholds else 'parameters'
                },
                'calculation_method': 'workout_plan_estimation',
                'estimated_at': datetime.now()
            }

        except Exception as e:
            logger.error(f"Error estimating workout plan TSS: {str(e)}")
            raise CalculationError(f"Workout plan TSS estimation failed: {str(e)}")

    def _estimate_power_segments_tss(self, segments: List[WorkoutPlanSegment], ftp: Optional[float]) -> Dict[str, Any]:
        """
        Estimate TSS for power-based segments.

        Linus approach: Generate fake data matching the target intensity,
        then use existing calculation logic. Simple and reuses existing code.
        """
        if ftp is None:
            ftp = self._estimate_ftp("workout_plan")
            if ftp is None:
                raise CalculationError("FTP required for power-based segments")

        total_tss = 0.0
        segment_results = []

        for segment in segments:
            # Generate simulated power data at target intensity
            duration_seconds = int(segment.duration_minutes * 60)
            simulated_power_data = [segment.target_value] * duration_seconds

            # Calculate segment TSS using existing logic
            try:
                segment_tss_result = self.calculate_power_tss(
                    raw_data=[{'power': p} for p in simulated_power_data],
                    ftp=ftp
                )

                segment_info = {
                    'duration_minutes': segment.duration_minutes,
                    'intensity_metric': 'power',
                    'target_value': segment.target_value,
                    'estimated_tss': segment_tss_result['tss'],
                    'intensity_factor': segment_tss_result['intensity_factor'],
                    'normalized_power': segment_tss_result['normalized_power']
                }

                segment_results.append(segment_info)
                total_tss += segment_tss_result['tss']

            except Exception as e:
                logger.warning(f"Failed to calculate TSS for power segment: {str(e)}")
                continue

        return {
            'total_tss': total_tss,
            'segments': segment_results
        }

    def _estimate_hr_segments_tss(self, segments: List[WorkoutPlanSegment],
                                 threshold_hr: Optional[int], max_hr: Optional[int]) -> Dict[str, Any]:
        """Estimate TSS for heart rate-based segments"""
        if threshold_hr is None:
            threshold_hr = self._estimate_threshold_hr()
            if threshold_hr is None:
                raise CalculationError("Threshold HR required for heart rate-based segments")

        if max_hr is None:
            max_hr = self._estimate_max_hr([])  # Use default estimation

        total_tss = 0.0
        segment_results = []

        for segment in segments:
            # Generate simulated HR data at target intensity
            duration_seconds = int(segment.duration_minutes * 60)
            simulated_hr_data = [int(segment.target_value)] * duration_seconds

            # Calculate segment TSS using existing logic
            try:
                segment_tss_result = self.calculate_hr_tss(
                    raw_data=[{'heart_rate': hr} for hr in simulated_hr_data],
                    threshold_hr=threshold_hr,
                    max_hr=max_hr
                )

                segment_info = {
                    'duration_minutes': segment.duration_minutes,
                    'intensity_metric': 'heart_rate',
                    'target_value': segment.target_value,
                    'estimated_tss': segment_tss_result['tss'],
                    'intensity_factor': segment_tss_result['intensity_factor'],
                    'avg_hr': segment_tss_result['avg_hr']
                }

                segment_results.append(segment_info)
                total_tss += segment_tss_result['tss']

            except Exception as e:
                logger.warning(f"Failed to calculate TSS for HR segment: {str(e)}")
                continue

        return {
            'total_tss': total_tss,
            'segments': segment_results
        }

    def _estimate_pace_segments_tss(self, segments: List[WorkoutPlanSegment],
                                   threshold_pace: Optional[float]) -> Dict[str, Any]:
        """Estimate TSS for pace-based segments"""
        if threshold_pace is None:
            threshold_pace = self._estimate_threshold_pace("workout_plan")
            if threshold_pace is None:
                raise CalculationError("Threshold pace required for pace-based segments")

        total_tss = 0.0
        segment_results = []

        for segment in segments:
            # Generate simulated speed data from target pace
            duration_seconds = int(segment.duration_minutes * 60)
            target_speed = self.pace_per_km_to_speed(segment.target_value)
            simulated_speed_data = [target_speed] * duration_seconds

            # Calculate segment TSS using existing logic
            try:
                segment_tss_result = self.calculate_running_pace_tss(
                    raw_data=[{'speed': speed} for speed in simulated_speed_data],
                    threshold_pace=threshold_pace
                )

                segment_info = {
                    'duration_minutes': segment.duration_minutes,
                    'intensity_metric': 'pace',
                    'target_value': segment.target_value,
                    'target_pace_formatted': self.format_pace(segment.target_value),
                    'estimated_tss': segment_tss_result['tss'],
                    'intensity_factor': segment_tss_result['intensity_factor'],
                    'normalized_pace': segment_tss_result['normalized_pace']
                }

                segment_results.append(segment_info)
                total_tss += segment_tss_result['tss']

            except Exception as e:
                logger.warning(f"Failed to calculate TSS for pace segment: {str(e)}")
                continue

        return {
            'total_tss': total_tss,
            'segments': segment_results
        }

    def _determine_primary_method(self, power_segments: List[WorkoutPlanSegment],
                                 hr_segments: List[WorkoutPlanSegment],
                                 pace_segments: List[WorkoutPlanSegment]) -> str:
        """
        Determine primary calculation method based on segment types.

        Follows the same priority as existing composite TSS: Power > HR > Pace
        """
        if power_segments:
            return 'power'
        elif hr_segments:
            return 'heart_rate'
        elif pace_segments:
            return 'pace'
        else:
            return 'unknown'
    
    def calculate_composite_tss(self, activity_id: str = None, raw_data: Optional[List[Dict[str, Any]]] = None, user_id: str = None, **kwargs) -> Dict[str, Any]:
        """
        Calculate TSS using the best available method based on data availability
        
        Priority: Power > Heart Rate > Pace
        
        Args:
            activity_id: Activity identifier (used if raw_data is None)
            raw_data: Optional list of record dictionaries containing fitness data
            user_id: User identifier (used to retrieve stored thresholds)
            **kwargs: Optional parameters for specific TSS calculations
            
        Returns:
            Dictionary containing TSS calculation results
        """
        results = {}
        
        # Get user thresholds if user_id is provided
        user_thresholds = {}
        if user_id:
            user_thresholds = self._get_user_thresholds(user_id)
            logger.debug(f"Retrieved user thresholds for {user_id}: {list(user_thresholds.keys())}")
        
        # Merge user thresholds with provided kwargs (kwargs take precedence)
        ftp = kwargs.get('ftp') or user_thresholds.get('ftp')
        threshold_power = kwargs.get('threshold_power') or user_thresholds.get('threshold_power')
        threshold_hr = kwargs.get('threshold_hr') or user_thresholds.get('threshold_hr')
        max_hr = kwargs.get('max_hr') or user_thresholds.get('max_hr')
        threshold_pace = kwargs.get('threshold_pace') or user_thresholds.get('threshold_pace')
        
        # Try power-based TSS first
        try:
            power_tss = self.calculate_power_tss(
                activity_id,
                ftp=ftp,
                threshold_power=threshold_power,
                raw_data=raw_data
            )
            results['power_tss'] = power_tss
            results['primary_method'] = 'power'
            results['tss'] = power_tss['tss']
        except (InsufficientDataError, CalculationError) as e:
            logger.debug(f"Power TSS not available: {str(e)}")
        
        # Try heart rate-based TSS
        try:
            hr_tss = self.calculate_hr_tss(
                activity_id,
                threshold_hr=threshold_hr,
                max_hr=max_hr,
                raw_data=raw_data
            )
            results['hr_tss'] = hr_tss
            if 'primary_method' not in results:
                results['primary_method'] = 'heart_rate'
                results['tss'] = hr_tss['tss']
        except (InsufficientDataError, CalculationError) as e:
            logger.debug(f"HR TSS not available: {str(e)}")
        
        # Try running pace-based TSS
        try:
            pace_tss = self.calculate_running_pace_tss(
                activity_id,
                threshold_pace=threshold_pace,
                raw_data=raw_data
            )
            results['pace_tss'] = pace_tss
            if 'primary_method' not in results:
                results['primary_method'] = 'running_pace'
                results['tss'] = pace_tss['tss']
        except (InsufficientDataError, CalculationError) as e:
            logger.debug(f"Running pace TSS not available: {str(e)}")
        
        if not results:
            raise InsufficientDataError("No suitable data available for TSS calculation")
        
        results['calculated_at'] = datetime.now()
        
        # Add threshold information used
        results['thresholds_used'] = {
            'ftp': ftp,
            'threshold_hr': threshold_hr,
            'max_hr': max_hr,
            'threshold_pace': threshold_pace,
            'source': 'user_indicators' if user_thresholds else 'parameters'
        }
        
        return results
    
    def _get_user_thresholds(self, user_id: str) -> Dict[str, Any]:
        """
        Get user threshold values from stored user indicators
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary containing user thresholds
        """
        try:
            user_indicators = self.storage.get_by_id(DataType.USER_INDICATOR, user_id)
            
            if user_indicators:
                return {
                    'threshold_hr': user_indicators.get('threshold_heart_rate'),
                    'max_hr': user_indicators.get('max_heart_rate'),
                    'resting_hr': user_indicators.get('resting_heart_rate'),
                    'ftp': user_indicators.get('threshold_power'),  # For backward compatibility
                    'threshold_power': user_indicators.get('threshold_power'),  # Running power terminology
                    'threshold_pace': user_indicators.get('threshold_pace'),
                    'weight': user_indicators.get('weight'),
                    'age': user_indicators.get('age'),
                    'gender': user_indicators.get('gender')
                }
        except Exception as e:
            logger.debug(f"Could not retrieve user thresholds for {user_id}: {str(e)}")
        
        return {}
    
    def calculate_and_index_tss(self, activity_id: str, user_id: str, **kwargs) -> Dict[str, Any]:
        """
        Calculate TSS for an activity and index the results to Elasticsearch
        
        Args:
            activity_id: Activity identifier
            user_id: User identifier
            **kwargs: Optional parameters for specific TSS calculations (ftp, threshold_hr, max_hr, threshold_pace)
            
        Returns:
            Dictionary containing TSS calculation results and indexing status
        """
        try:
            # Calculate composite TSS
            tss_results = self.calculate_composite_tss(activity_id, user_id=user_id, **kwargs)
            
            # Get activity context from session data
            activity_context = self._get_activity_context(activity_id)
            
            # Prepare document for indexing
            tss_doc = self._prepare_tss_document(
                activity_id=activity_id,
                user_id=user_id,
                tss_results=tss_results,
                activity_context=activity_context
            )
            
            # Index to Elasticsearch
            doc_id = f"{user_id}_{activity_id}"
            success = self.storage.index_document(DataType.TSS, doc_id, tss_doc)
            
            if success:
                logger.info(f"✅ Successfully indexed TSS for activity {activity_id}")
                tss_results['indexing_status'] = 'success'
                tss_results['doc_id'] = doc_id
            else:
                logger.error(f"❌ Failed to index TSS for activity {activity_id}")
                tss_results['indexing_status'] = 'failed'
            
            return tss_results
            
        except Exception as e:
            error_msg = f"Failed to calculate and index TSS for activity {activity_id}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                'error': error_msg,
                'indexing_status': 'failed',
                'activity_id': activity_id,
                'user_id': user_id,
                'calculated_at': datetime.now()
            }
    
    def batch_calculate_and_index_tss(self, activities: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """
        Batch calculate and index TSS for multiple activities
        
        Args:
            activities: List of activities with 'activity_id' and 'user_id'
            **kwargs: Optional parameters for TSS calculations
            
        Returns:
            Dictionary containing batch processing results
        """
        results = {
            'total': len(activities),
            'successful': 0,
            'failed': 0,
            'details': [],
            'started_at': datetime.now()
        }
        
        tss_documents = []
        
        for activity in activities:
            try:
                activity_id = activity['activity_id']
                user_id = activity['user_id']
                
                # Calculate composite TSS
                tss_results = self.calculate_composite_tss(activity_id, user_id=user_id, **kwargs)
                
                # Get activity context
                activity_context = self._get_activity_context(activity_id)
                
                # Prepare document for bulk indexing
                tss_doc = self._prepare_tss_document(
                    activity_id=activity_id,
                    user_id=user_id,
                    tss_results=tss_results,
                    activity_context=activity_context
                )
                
                # Add document ID for bulk indexing
                tss_doc['_id'] = f"{user_id}_{activity_id}"
                tss_documents.append(tss_doc)
                
                results['successful'] += 1
                results['details'].append({
                    'activity_id': activity_id,
                    'user_id': user_id,
                    'status': 'success',
                    'tss': tss_results.get('tss', 0),
                    'primary_method': tss_results.get('primary_method', 'unknown')
                })
                
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'activity_id': activity.get('activity_id', 'unknown'),
                    'user_id': activity.get('user_id', 'unknown'),
                    'status': 'failed',
                    'error': str(e)
                })
                logger.error(f"❌ Failed to calculate TSS for activity {activity.get('activity_id', 'unknown')}: {str(e)}")
        
        # Bulk index documents
        if tss_documents:
            try:
                indexing_result = self.storage.bulk_index(DataType.TSS, tss_documents)
                results['indexing_result'] = {
                    'success_count': indexing_result.success_count,
                    'failed_count': indexing_result.failed_count,
                    'errors': indexing_result.errors
                }
                logger.info(f"✅ Bulk indexed {indexing_result.success_count} TSS documents")
            except Exception as e:
                results['indexing_error'] = str(e)
                logger.error(f"❌ Bulk indexing failed: {str(e)}")
        
        results['completed_at'] = datetime.now()
        results['duration'] = (results['completed_at'] - results['started_at']).total_seconds()
        
        return results
    
    def get_tss_by_activity(self, activity_id: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve TSS data for a specific activity from Elasticsearch
        
        Args:
            activity_id: Activity identifier
            user_id: User identifier (optional, used for document ID if provided)
            
        Returns:
            TSS data if found, None otherwise
        """
        try:
            if user_id:
                # Try direct document lookup first
                doc_id = f"{user_id}_{activity_id}"
                result = self.storage.get_by_id(DataType.TSS, doc_id)
                if result:
                    return result
            
            # Fall back to search by activity_id
            query_filter = (QueryFilter()
                           .add_term_filter("activity_id", activity_id))
            
            if user_id:
                query_filter.add_term_filter("user_id", user_id)
            
            results = self.storage.search(DataType.TSS, query_filter)
            return results[0] if results else None
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve TSS for activity {activity_id}: {str(e)}")
            return None
    
    def get_user_tss_history(self, user_id: str, start_date: datetime = None, end_date: datetime = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Retrieve TSS history for a user
        
        Args:
            user_id: User identifier
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum number of records to return
            
        Returns:
            List of TSS records
        """
        try:
            query_filter = (QueryFilter()
                           .add_term_filter("user_id", user_id)
                           .add_sort("timestamp", ascending=False)
                           .set_pagination(limit))
            
            if start_date or end_date:
                query_filter.add_date_range("timestamp", start_date, end_date)
            
            return self.storage.search(DataType.TSS, query_filter)
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve TSS history for user {user_id}: {str(e)}")
            return []
    
    def _get_activity_context(self, activity_id: str) -> Dict[str, Any]:
        """
        Get activity context information from session data
        
        Args:
            activity_id: Activity identifier
            
        Returns:
            Dictionary containing activity context
        """
        try:
            # Get session data
            query_filter = (QueryFilter()
                           .add_term_filter("activity_id", activity_id)
                           .set_pagination(1))
            
            sessions = self.storage.search(DataType.SESSION, query_filter)
            if sessions:
                session = sessions[0]
                return {
                    'sport': session.get('sport', 'unknown'),
                    'sub_sport': session.get('sub_sport', ''),
                    'total_distance': session.get('total_distance', 0),
                    'total_duration': session.get('total_timer_time', 0),
                    'total_calories': session.get('total_calories', 0),
                    'timestamp': session.get('timestamp'),
                    'start_time': session.get('start_time')
                }
        except Exception as e:
            logger.debug(f"Could not get activity context for {activity_id}: {str(e)}")
        
        return {
            'sport': 'unknown',
            'sub_sport': '',
            'total_distance': 0,
            'total_duration': 0,
            'total_calories': 0,
            'timestamp': datetime.now().isoformat(),
            'start_time': None
        }
    
    def _prepare_tss_document(self, activity_id: str, user_id: str, tss_results: Dict[str, Any], activity_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare TSS document for indexing
        
        Args:
            activity_id: Activity identifier
            user_id: User identifier
            tss_results: TSS calculation results
            activity_context: Activity context information
            
        Returns:
            Document ready for indexing
        """
        doc = {
            'activity_id': activity_id,
            'user_id': user_id,
            'timestamp': activity_context.get('timestamp') or datetime.now().isoformat(),
            'calculated_at': tss_results.get('calculated_at', datetime.now()).isoformat(),
            
            # Activity context
            'sport': activity_context.get('sport', 'unknown'),
            'sub_sport': activity_context.get('sub_sport', ''),
            'total_distance': activity_context.get('total_distance', 0),
            'total_duration': activity_context.get('total_duration', 0),
            'total_calories': activity_context.get('total_calories', 0),
            
            # Composite TSS info
            'primary_method': tss_results.get('primary_method', 'unknown'),
            'primary_tss': tss_results.get('tss', 0),
            'available_methods': list(tss_results.keys()),
            
            # Quality and metadata
            'quality_score': 1.0,  # Default high quality
            'confidence': 'high',
            'warnings': [],
            'errors': []
        }
        
        # Add power TSS data if available
        if 'power_tss' in tss_results:
            power_data = tss_results['power_tss']
            doc['power_tss'] = {
                'tss': power_data.get('tss', 0),
                'normalized_power': power_data.get('normalized_power', 0),
                'intensity_factor': power_data.get('intensity_factor', 0),
                'functional_threshold_power': power_data.get('ftp', 0),
                'duration_hours': power_data.get('duration_hours', 0),
                'method': 'power'
            }
        
        # Add HR TSS data if available
        if 'hr_tss' in tss_results:
            hr_data = tss_results['hr_tss']
            doc['hr_tss'] = {
                'tss': hr_data.get('tss', 0),
                'intensity_factor': hr_data.get('intensity_factor', 0),
                'threshold_hr': hr_data.get('threshold_hr', 0),
                'max_hr': hr_data.get('max_hr', 0),
                'avg_hr': hr_data.get('avg_hr', 0),
                'duration_hours': hr_data.get('duration_hours', 0),
                'method': 'heart_rate'
            }
        
        # Add pace TSS data if available
        if 'pace_tss' in tss_results:
            pace_data = tss_results['pace_tss']
            doc['rtss'] = {
                'tss': pace_data.get('tss', 0),
                'normalized_pace': pace_data.get('normalized_pace', 0),
                'intensity_factor': pace_data.get('intensity_factor', 0),
                'threshold_pace': pace_data.get('threshold_pace', 0),
                'avg_pace': pace_data.get('avg_pace', 0),
                'duration_hours': pace_data.get('duration_hours', 0),
                'method': 'running_pace'
            }
        
        return doc
    
    def _get_power_data(self, activity_id: str = None, raw_data: Optional[List[Dict[str, Any]]] = None) -> List[float]:
        """Get power data for an activity from storage or raw data"""
        if raw_data is not None:
            # Use provided raw data - check multiple power field variations
            power_data = []
            for r in raw_data:
                power_val = self._extract_power_value(r)
                if power_val and power_val > 0:
                    power_data.append(power_val)
            return power_data
        
        if activity_id is None:
            raise ValueError("Either activity_id or raw_data must be provided")
        
        query_filter = (QueryFilter()
                       .add_term_filter("activity_id", activity_id)
                       .add_sort("timestamp", ascending=True)
                       .set_pagination(10000))
        
        records = self.storage.search(DataType.RECORD, query_filter)
        power_data = []
        for r in records:
            power_val = self._extract_power_value(r)
            if power_val and power_val > 0:
                power_data.append(power_val)
        return power_data
    
    def _extract_power_value(self, record: Dict[str, Any]) -> Optional[float]:
        """Extract power value from a record, checking multiple field name variations"""
        # Check common power field variations
        power_fields = ['power', 'Power', 'enhanced_power', 'avg_power']
        
        for field in power_fields:
            if field in record and record[field] is not None:
                try:
                    power_val = float(record[field])
                    if power_val > 0:
                        return power_val
                except (ValueError, TypeError):
                    continue
        
        # Check power_fields nested object
        if 'power_fields' in record and isinstance(record['power_fields'], dict):
            power_fields_obj = record['power_fields']
            for field in ['power', 'avg_power']:
                if field in power_fields_obj and power_fields_obj[field] is not None:
                    try:
                        power_val = float(power_fields_obj[field])
                        if power_val > 0:
                            return power_val
                    except (ValueError, TypeError):
                        continue
        
        return None
    
    def _get_heart_rate_data(self, activity_id: str = None, raw_data: Optional[List[Dict[str, Any]]] = None) -> List[int]:
        """Get heart rate data for an activity from storage or raw data"""
        if raw_data is not None:
            # Use provided raw data
            hr_data = [r.get('heart_rate', 0) for r in raw_data if r.get('heart_rate') and r.get('heart_rate') > 0]
            return hr_data
        
        if activity_id is None:
            raise ValueError("Either activity_id or raw_data must be provided")
        
        query_filter = (QueryFilter()
                       .add_term_filter("activity_id", activity_id)
                       .add_sort("timestamp", ascending=True)
                       .set_pagination(10000))
        
        records = self.storage.search(DataType.RECORD, query_filter)
        hr_data = [r.get('heart_rate', 0) for r in records if r.get('heart_rate') and r.get('heart_rate') > 0]
        return hr_data
    
    def _get_speed_data(self, activity_id: str = None, raw_data: Optional[List[Dict[str, Any]]] = None) -> List[float]:
        """Get speed data for an activity from storage or raw data"""
        if raw_data is not None:
            # Use provided raw data
            speed_data = []
            for r in raw_data:
                speed_val = self._extract_speed_value(r)
                if speed_val and speed_val > 0:
                    speed_data.append(speed_val)
            return speed_data
        
        if activity_id is None:
            raise ValueError("Either activity_id or raw_data must be provided")
        
        query_filter = (QueryFilter()
                       .add_term_filter("activity_id", activity_id)
                       .add_sort("timestamp", ascending=True)
                       .set_pagination(10000))
        
        records = self.storage.search(DataType.RECORD, query_filter)
        speed_data = []
        
        for r in records:
            speed_val = self._extract_speed_value(r)
            if speed_val and speed_val > 0:
                speed_data.append(speed_val)
        
        return speed_data
    
    def _extract_speed_value(self, record: Dict[str, Any]) -> Optional[float]:
        """Extract speed value from a record, checking multiple field name variations"""
        # Check common speed field variations
        speed_fields = ['speed', 'enhanced_speed', 'avg_speed']
        
        for field in speed_fields:
            if field in record and record[field] is not None:
                try:
                    speed_val = float(record[field])
                    if speed_val > 0:
                        return speed_val
                except (ValueError, TypeError):
                    continue
        
        # Check additional_fields nested object
        if 'additional_fields' in record and isinstance(record['additional_fields'], dict):
            additional = record['additional_fields']
            for field in ['enhanced_speed', 'speed']:
                if field in additional and additional[field] is not None:
                    try:
                        speed_val = float(additional[field])
                        if speed_val > 0:
                            return speed_val
                    except (ValueError, TypeError):
                        continue
        
        # Check speed_metrics nested object
        if 'speed_metrics' in record and isinstance(record['speed_metrics'], dict):
            speed_metrics = record['speed_metrics']
            for field in ['avg_speed', 'speed']:
                if field in speed_metrics and speed_metrics[field] is not None:
                    try:
                        speed_val = float(speed_metrics[field])
                        if speed_val > 0:
                            return speed_val
                    except (ValueError, TypeError):
                        continue
        
        return None
    
    def _get_pace_data(self, activity_id: str = None, raw_data: Optional[List[Dict[str, Any]]] = None) -> List[float]:
        """Get pace data for an activity (converted from speed to min/km) from storage or raw data"""
        speed_data = self._get_speed_data(activity_id, raw_data=raw_data)
        pace_data = [self.speed_to_pace_per_km(speed) for speed in speed_data if speed > 0]
        return pace_data
    
    def _calculate_normalized_power(self, power_data: List[float]) -> float:
        """
        Calculate Normalized Power (NP) using 30-second rolling average
        NP = (average of (30-sec power)^4)^(1/4)
        """
        if len(power_data) < 30:
            return mean(power_data) if power_data else 0
        
        # Calculate 30-second rolling averages
        rolling_powers = []
        for i in range(len(power_data) - 29):
            avg_30s = mean(power_data[i:i+30])
            rolling_powers.append(avg_30s ** 4)
        
        if not rolling_powers:
            return mean(power_data)
        
        # Calculate NP
        avg_power_4 = mean(rolling_powers)
        normalized_power = avg_power_4 ** (1/4)
        
        return normalized_power
    
    def _calculate_normalized_pace(self, pace_data: List[float]) -> float:
        """
        Calculate Normalized Graded Pace equivalent for running
        Similar to normalized power but for pace data (min/km)
        
        For pace, we need to be careful because:
        - Faster pace = lower time per km = higher intensity
        - We want to weight faster sections more heavily
        """
        if len(pace_data) < 30:
            return mean(pace_data) if pace_data else 0
        
        # Calculate 30-second rolling averages
        rolling_paces = []
        for i in range(len(pace_data) - 29):
            avg_30s_pace = mean(pace_data[i:i+30])
            
            # For pace calculation, we need to convert to speed for the power calculation
            # then convert back to pace for the final result
            if avg_30s_pace > 0:
                speed_equivalent = self.pace_per_km_to_speed(avg_30s_pace)
                rolling_paces.append(speed_equivalent ** 4)
            else:
                rolling_paces.append(0)
        
        if not rolling_paces:
            return mean(pace_data)
        
        # Calculate normalized speed first, then convert back to pace
        avg_speed_4 = mean(rolling_paces)
        normalized_speed = avg_speed_4 ** (1/4) if avg_speed_4 > 0 else 0
        
        # Convert back to pace
        normalized_pace = self.speed_to_pace_per_km(normalized_speed) if normalized_speed > 0 else mean(pace_data)
        
        return normalized_pace
    
    def _calculate_hr_intensity_factor(self, hr_data: List[int], threshold_hr: int, max_hr: int) -> float:
        """
        Calculate heart rate-based intensity factor using TRIMP method
        """
        if not hr_data or threshold_hr <= 0:
            return 0.0
        
        total_trimp = 0.0
        threshold_trimp = 0.0
        
        for hr in hr_data:
            # Calculate relative intensity
            hr_ratio = min(hr / max_hr, 1.0) if max_hr > 0 else 0.5
            
            # TRIMP calculation with exponential weighting
            trimp_factor = 0.64 * np.exp(1.92 * hr_ratio) if hr_ratio > 0.5 else hr_ratio
            total_trimp += trimp_factor
            
            # Calculate what TRIMP would be at threshold
            threshold_ratio = threshold_hr / max_hr if max_hr > 0 else 0.85
            threshold_trimp_factor = 0.64 * np.exp(1.92 * threshold_ratio) if threshold_ratio > 0.5 else threshold_ratio
            threshold_trimp += threshold_trimp_factor
        
        # Intensity factor is the ratio of actual TRIMP to threshold TRIMP
        intensity_factor = total_trimp / threshold_trimp if threshold_trimp > 0 else 0.0
        
        return min(intensity_factor, 2.0)  # Cap at 2.0 for safety
    
    def _estimate_ftp(self, activity_ref: str) -> Optional[float]:
        """Estimate FTP from power zones in thresholds
        
        Args:
            activity_ref: Activity identifier or reference (used for logging)
        """
        if self.thresholds and self.thresholds.power_zones:
            # FTP is typically the upper bound of Zone 3 or lower bound of Zone 4
            for zone_name, (min_power, max_power) in self.thresholds.power_zones.items():
                if 'zone_4' in zone_name.lower() or 'threshold' in zone_name.lower():
                    return float(min_power)
            # Fallback: use zone_3 upper bound
            for zone_name, (min_power, max_power) in self.thresholds.power_zones.items():
                if 'zone_3' in zone_name.lower():
                    return float(max_power)
        
        # Default fallback FTP for demo purposes
        logger.debug("No power zones defined, using default FTP of 250W")
        return 250.0
    
    def _estimate_threshold_hr(self) -> Optional[int]:
        """Estimate threshold HR from heart rate zones"""
        if self.thresholds and self.thresholds.heart_rate_zones:
            # Threshold HR is typically the upper bound of Zone 3 or lower bound of Zone 4
            for zone_name, (min_hr, max_hr) in self.thresholds.heart_rate_zones.items():
                if 'zone_4' in zone_name.lower() or 'threshold' in zone_name.lower():
                    return int(min_hr)
            # Fallback: use zone_3 upper bound
            for zone_name, (min_hr, max_hr) in self.thresholds.heart_rate_zones.items():
                if 'zone_3' in zone_name.lower():
                    return int(max_hr)
        
        # Default fallback threshold HR for demo purposes
        logger.debug("No heart rate zones defined, using default threshold HR of 170 bpm")
        return 170
    
    def _estimate_threshold_pace(self, activity_ref: str) -> Optional[float]:
        """Estimate threshold pace from pace zones (in min/km format)
        
        Args:
            activity_ref: Activity identifier or reference (used for logging)
        """
        if self.thresholds and self.thresholds.pace_zones:
            # Threshold pace is typically Zone 4 or threshold zone
            for zone_name, (_, max_pace) in self.thresholds.pace_zones.items():
                if 'zone_4' in zone_name.lower() or 'threshold' in zone_name.lower():
                    return float(max_pace)  # For pace, higher values are slower
            # Fallback: use zone_3 upper bound
            for zone_name, (_, max_pace) in self.thresholds.pace_zones.items():
                if 'zone_3' in zone_name.lower():
                    return float(max_pace)
        
        # Default fallback threshold pace for demo purposes (4:00/km)
        logger.debug("No pace zones defined, using default threshold pace of 4.0 min/km")
        return 4.0
    
    def _estimate_max_hr(self, hr_data: List[int]) -> int:
        """Estimate max HR from data or use age-based formula"""
        if hr_data:
            # Use 95th percentile of observed HR data
            return int(np.percentile(hr_data, 95))
        else:
            # Default age-based estimate (220 - age), assume age 35
            return 185


class TSSAnalyzer:
    """High-level TSS analyzer with reporting capabilities"""
    
    def __init__(self, storage: StorageInterface, thresholds: Optional[MetricThresholds] = None):
        self.storage = storage
        self.calculator = TSSCalculator(storage, thresholds)
    
    def analyze_training_stress(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """
        Analyze training stress over a time period
        
        Args:
            filter_criteria: Analytics filter criteria
            
        Returns:
            AnalyticsResult containing TSS analysis
        """
        try:
            start_date, end_date = filter_criteria.time_range.to_dates()
            
            if not start_date or not end_date:
                raise ValueError("Time range must be specified for TSS analysis")
            
            # Get all activities in the time range
            query_filter = (QueryFilter()
                           .add_term_filter("user_id", filter_criteria.user_id)
                           .add_date_range("timestamp", start=start_date, end=end_date))
            
            if filter_criteria.sport_types:
                # Note: This would need to be implemented as an "OR" filter in the storage layer
                pass
            
            activities = self.storage.search(DataType.SESSION, query_filter)
            
            total_tss = 0.0
            activity_tss = []
            sport_breakdown = {}
            
            for activity in activities:
                activity_id = activity.get('activity_id')
                sport = activity.get('sport', 'unknown')
                
                try:
                    tss_result = self.calculator.calculate_composite_tss(activity_id)
                    tss_value = tss_result.get('tss', 0)
                    
                    total_tss += tss_value
                    activity_tss.append({
                        'activity_id': activity_id,
                        'sport': sport,
                        'tss': tss_value,
                        'method': tss_result.get('primary_method'),
                        'date': activity.get('timestamp', start_date).isoformat()
                    })
                    
                    # Sport breakdown
                    if sport not in sport_breakdown:
                        sport_breakdown[sport] = {'tss': 0.0, 'count': 0}
                    sport_breakdown[sport]['tss'] += tss_value
                    sport_breakdown[sport]['count'] += 1
                    
                except Exception as e:
                    logger.warning(f"Could not calculate TSS for activity {activity_id}: {str(e)}")
                    continue
            
            # Calculate weekly averages
            days_in_period = (end_date - start_date).days
            weeks_in_period = max(days_in_period / 7, 1)
            
            analysis_data = {
                'total_tss': round(total_tss, 1),
                'avg_weekly_tss': round(total_tss / weeks_in_period, 1),
                'avg_daily_tss': round(total_tss / max(days_in_period, 1), 1),
                'activity_count': len(activity_tss),
                'sport_breakdown': sport_breakdown,
                'activity_tss': activity_tss,
                'period_days': days_in_period,
                'training_load_category': self._categorize_training_load(total_tss / weeks_in_period)
            }
            
            return AnalyticsResult(
                analytics_type=AnalyticsType.TRAINING_LOAD,
                data=analysis_data,
                metadata={
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'user_id': filter_criteria.user_id
                },
                generated_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error in TSS analysis: {str(e)}")
            raise CalculationError(f"TSS analysis failed: {str(e)}")
    
    def _categorize_training_load(self, weekly_tss: float) -> str:
        """Categorize training load based on weekly TSS"""
        if weekly_tss < 150:
            return "low"
        elif weekly_tss < 300:
            return "moderate"
        elif weekly_tss < 450:
            return "high"
        else:
            return "very_high"

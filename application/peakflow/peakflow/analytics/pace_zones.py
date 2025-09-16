#!/usr/bin/env python3
"""
Pace Zones Analytics Module

This module provides comprehensive pace zone calculations based on various
methodologies for running training including:
- Jack Daniels VDOT-based (5 zones) - Classic running zones using VDOT
- Joe Friel Running (7 zones) - Threshold pace based zones
- PZI (Pace Zone Index) (10 zones) - TrainingPeaks comprehensive system
- USAT Running (6 zones) - USA Triathlon methodology
- 80/20 Running (7 zones) - Polarized training approach

Each method provides pace ranges with detailed explanations of training purposes
and physiological adaptations for optimal training prescription.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple, Union
import math

from .interface import (
    AnalyticsFilter, AnalyticsResult, AnalyticsType, MetricThresholds,
    FitnessAnalyzer, AnalyticsError, InvalidParameterError
)
from ..utils import get_logger

logger = get_logger(__name__)


class PaceZoneMethod(Enum):
    """Available pace zone calculation methods"""
    JACK_DANIELS = "jack_daniels"  # 5 zones - VDOT based
    JOE_FRIEL = "joe_friel"  # 7 zones - Threshold pace based  
    PZI = "pzi"  # 10 zones - Pace Zone Index
    USAT_RUNNING = "usat_running"  # 6 zones - USA Triathlon
    EIGHTY_TWENTY_RUNNING = "80_20_running"  # 7 zones - Polarized training


@dataclass
class PaceZone:
    """Represents a single pace training zone"""
    zone_number: int
    zone_name: str
    pace_range: Tuple[float, float]  # (min_pace, max_pace) in seconds per km
    percentage_range: Optional[Tuple[float, float]] = None  # Percentage of threshold/VDOT pace
    description: str = ""
    purpose: str = ""
    training_benefits: List[str] = field(default_factory=list)
    duration_guidelines: str = ""
    intensity_feel: str = ""
    target_distances: List[str] = field(default_factory=list)
    
    def get_pace_per_mile(self) -> Tuple[float, float]:
        """Convert pace from seconds per km to seconds per mile"""
        km_to_mile = 1.609344
        return (self.pace_range[0] * km_to_mile, self.pace_range[1] * km_to_mile)
    
    def format_pace_per_km(self) -> Tuple[str, str]:
        """Format pace as MM:SS per km"""
        def seconds_to_mmss(seconds: float) -> str:
            if seconds == float('inf') or seconds != seconds:  # Check for inf or NaN
                return "inf"
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}:{secs:02d}"
        
        return (seconds_to_mmss(self.pace_range[0]), seconds_to_mmss(self.pace_range[1]))
    
    def format_pace_per_mile(self) -> Tuple[str, str]:
        """Format pace as MM:SS per mile"""
        pace_per_mile = self.get_pace_per_mile()
        def seconds_to_mmss(seconds: float) -> str:
            if seconds == float('inf') or seconds != seconds:  # Check for inf or NaN
                return "inf"
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}:{secs:02d}"
        
        return (seconds_to_mmss(pace_per_mile[0]), seconds_to_mmss(pace_per_mile[1]))


@dataclass 
class PaceZoneResult:
    """Result containing pace zone calculations and analysis"""
    method: PaceZoneMethod
    method_name: str
    threshold_pace: Optional[float]  # seconds per km
    vdot: Optional[float] = None
    reference_time: Optional[Tuple[float, float]] = None  # (distance_km, time_seconds)
    zones: List[PaceZone] = field(default_factory=list)
    method_description: str = ""
    recommendations: List[str] = field(default_factory=list)
    calculated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format"""
        return {
            'method': self.method.value,
            'method_name': self.method_name,
            'threshold_pace': self.threshold_pace,
            'vdot': self.vdot,
            'reference_time': self.reference_time,
            'zones': [
                {
                    'zone_number': z.zone_number,
                    'zone_name': z.zone_name,
                    'pace_range_per_km': z.pace_range,
                    'pace_range_per_mile': z.get_pace_per_mile(),
                    'pace_formatted_per_km': z.format_pace_per_km(),
                    'pace_formatted_per_mile': z.format_pace_per_mile(),
                    'percentage_range': z.percentage_range,
                    'description': z.description,
                    'purpose': z.purpose,
                    'training_benefits': z.training_benefits,
                    'duration_guidelines': z.duration_guidelines,
                    'intensity_feel': z.intensity_feel,
                    'target_distances': z.target_distances
                } for z in self.zones
            ],
            'method_description': self.method_description,
            'recommendations': self.recommendations,
            'calculated_at': self.calculated_at.isoformat()
        }


class PaceZoneCalculator(ABC):
    """Abstract base class for pace zone calculators"""
    
    @abstractmethod
    def calculate_zones(self, **kwargs) -> PaceZoneResult:
        """Calculate pace zones based on input parameters"""
        pass
    
    @staticmethod
    def race_time_to_vdot(distance_km: float, time_seconds: float) -> float:
        """
        Calculate VDOT from race time using Jack Daniels' formula
        
        Args:
            distance_km: Race distance in kilometers
            time_seconds: Race time in seconds
            
        Returns:
            VDOT value
        """
        import math
        
        # Convert to time in minutes and velocity in meters/minute
        time_minutes = time_seconds / 60
        velocity = (distance_km * 1000) / time_minutes  # m/min
        
        # Jack Daniels VDOT formula for VO2 demand
        # VO2 = -4.6 + 0.182258 * (velocity) + 0.000104 * (velocity^2)
        vo2_demand = -4.6 + 0.182258 * velocity + 0.000104 * (velocity ** 2)
        
        # Jack Daniels' exponential decay formula for percentage of VO2max
        # This accounts for the fact that longer races are run at lower percentages of VO2max
        percent_vo2max = (
            0.8
            + 0.1894393 * math.exp(-0.012778 * time_minutes)
            + 0.2989558 * math.exp(-0.1932605 * time_minutes)
        )
        
        # Calculate VDOT (VO2max equivalent)
        vdot = vo2_demand / percent_vo2max
        
        return max(30.0, min(85.0, round(vdot, 1)))  # Reasonable bounds with rounding
    
    @staticmethod
    def vdot_to_pace(vdot: float, pace_type: str) -> float:
        """
        Convert VDOT to training pace in seconds per km
        
        Args:
            vdot: VDOT value
            pace_type: Type of pace ('E', 'M', 'T', 'I', 'R')
            
        Returns:
            Pace in seconds per km
        """
        # Base velocity for vVO2max (roughly I pace)
        base_velocity = 15.3 * vdot  # m/min
        
        # Pace adjustments based on Jack Daniels' tables
        if pace_type == 'E':  # Easy
            velocity = base_velocity * 0.75  # ~75% vVO2max
        elif pace_type == 'M':  # Marathon
            velocity = base_velocity * 0.85  # ~85% vVO2max
        elif pace_type == 'T':  # Threshold
            velocity = base_velocity * 0.88  # ~88% vVO2max
        elif pace_type == 'I':  # Interval (vVO2max)
            velocity = base_velocity  # 100% vVO2max
        elif pace_type == 'R':  # Repetition
            velocity = base_velocity * 1.1  # ~110% vVO2max
        else:
            velocity = base_velocity
        
        # Convert velocity (m/min) to pace (sec/km)
        pace_per_km = (1000 / velocity) * 60
        
        return pace_per_km
    
    def _calculate_pace_from_percentage(self, reference_pace: float, percentage: float) -> float:
        """
        Calculate pace from percentage of reference pace
        Note: Higher percentage = slower pace for pace calculations
        """
        return reference_pace * (percentage / 100)
    
    def _create_zone(self, zone_num: int, zone_name: str, 
                    min_pace: float, max_pace: float,
                    percentage_range: Optional[Tuple[float, float]] = None,
                    description: str = "", purpose: str = "",
                    benefits: Optional[List[str]] = None,
                    duration: str = "", intensity: str = "",
                    distances: Optional[List[str]] = None) -> PaceZone:
        """Helper method to create a pace zone"""
        return PaceZone(
            zone_number=zone_num,
            zone_name=zone_name,
            pace_range=(min_pace, max_pace),
            percentage_range=percentage_range,
            description=description,
            purpose=purpose,
            training_benefits=benefits or [],
            duration_guidelines=duration,
            intensity_feel=intensity,
            target_distances=distances or []
        )


class JackDanielsCalculator(PaceZoneCalculator):
    """
    Jack Daniels VDOT-based Pace Zone Calculator (5 zones)
    
    Based on Dr. Jack Daniels' "Daniels' Running Formula" using VDOT
    (VO2max corrected for running economy) to determine training paces.
    """
    
    def calculate_zones(self, vdot: Optional[float] = None, 
                       distance_km: Optional[float] = None,
                       time_seconds: Optional[float] = None) -> PaceZoneResult:
        """
        Calculate Jack Daniels pace zones from VDOT or race performance
        
        Args:
            vdot: Direct VDOT value
            distance_km: Race distance in km (alternative to VDOT)
            time_seconds: Race time in seconds (alternative to VDOT)
        """
        if vdot is None:
            if distance_km is None or time_seconds is None:
                raise InvalidParameterError("Either VDOT or race performance (distance_km and time_seconds) must be provided")
            vdot = self.race_time_to_vdot(distance_km, time_seconds)
            reference_time = (distance_km, time_seconds)
        else:
            reference_time = None
        
        # Calculate training paces using VDOT
        easy_pace = self.vdot_to_pace(vdot, 'E')
        marathon_pace = self.vdot_to_pace(vdot, 'M')
        threshold_pace = self.vdot_to_pace(vdot, 'T')
        interval_pace = self.vdot_to_pace(vdot, 'I')
        repetition_pace = self.vdot_to_pace(vdot, 'R')
        
        zones = [
            self._create_zone(
                1, "Easy/Long (E)", easy_pace * 1.15, easy_pace * 0.95,
                percentage_range=(95, 115),
                description="Comfortable running pace for building aerobic base and recovery",
                purpose="Develop cardiovascular and muscular systems with minimal stress",
                benefits=[
                    "Improved oxygen delivery to muscles",
                    "Enhanced fat metabolism", 
                    "Strengthened running muscles",
                    "Mental relaxation and enjoyment"
                ],
                duration="30 minutes to several hours",
                intensity="Comfortable, conversational pace",
                distances=["Easy runs", "Long runs", "Recovery runs"]
            ),
            self._create_zone(
                2, "Marathon (M)", marathon_pace * 1.05, marathon_pace * 0.95,
                percentage_range=(95, 105),
                description="Marathon race pace for specific marathon preparation",
                purpose="Prepare body for marathon race demands and pacing",
                benefits=[
                    "Marathon-specific preparation",
                    "Improved running economy",
                    "Mental race preparation",
                    "Pace judgment skills"
                ],
                duration="20 minutes to 2+ hours",
                intensity="Steady, controlled effort",
                distances=["Marathon pace runs", "Long tempo runs"]
            ),
            self._create_zone(
                3, "Threshold (T)", threshold_pace * 1.02, threshold_pace * 0.98,
                percentage_range=(98, 102),
                description="Comfortably hard pace at lactate threshold intensity",
                purpose="Improve ability to clear lactate and run at threshold",
                benefits=[
                    "Increased lactate clearance",
                    "Improved threshold pace",
                    "Enhanced endurance",
                    "Better tempo running"
                ],
                duration="20-40 minutes total per session",
                intensity="Comfortably hard, focused effort",
                distances=["Tempo runs", "Threshold intervals", "15K-Half marathon pace"]
            ),
            self._create_zone(
                4, "Interval (I)", interval_pace * 1.02, interval_pace * 0.98,
                percentage_range=(98, 102),
                description="Hard pace that stresses aerobic system near VO2max",
                purpose="Improve VO2max and running economy at high speeds",
                benefits=[
                    "Increased VO2max",
                    "Improved running economy",
                    "Enhanced oxygen utilization",
                    "Better 5K-10K performance"
                ],
                duration="3-5 minutes per rep, up to 8% of weekly mileage",
                intensity="Hard, rhythmic breathing",
                distances=["5K pace", "VO2max intervals", "Track intervals"]
            ),
            self._create_zone(
                5, "Repetition (R)", repetition_pace * 1.03, repetition_pace * 0.97,
                percentage_range=(97, 103),
                description="Fast pace for improving speed and running mechanics",
                purpose="Improve anaerobic power, speed, and running economy",
                benefits=[
                    "Enhanced running mechanics",
                    "Improved neuromuscular power",
                    "Better anaerobic capacity",
                    "Increased stride efficiency"
                ],
                duration="30 seconds to 2 minutes per rep, up to 5% of weekly mileage",
                intensity="Fast, controlled speed",
                distances=["Mile pace", "Speed intervals", "Track repeats"]
            )
        ]
        
        return PaceZoneResult(
            method=PaceZoneMethod.JACK_DANIELS,
            method_name="Jack Daniels VDOT (5 zones)",
            threshold_pace=threshold_pace,
            vdot=vdot,
            reference_time=reference_time,
            zones=zones,
            method_description=(
                "Jack Daniels' VDOT-based training system uses five distinct pace zones "
                "calculated from current fitness level (VDOT). Each zone targets specific "
                "physiological adaptations with precise pace ranges derived from running "
                "economy and VO2max relationships. This system emphasizes quality over "
                "quantity and provides scientific basis for training intensities."
            ),
            recommendations=[
                "Easy runs should comprise 80% or more of total training time",
                "Threshold runs: limit to 10% of weekly mileage or 60 minutes per session",
                "Interval work: maximum 8% of weekly mileage, 3-5 minute reps",
                "Repetition work: maximum 5% of weekly mileage, focus on form",
                "Allow adequate recovery between quality sessions",
                "Adjust paces based on environmental conditions and fatigue"
            ]
        )


class JoeFrielCalculator(PaceZoneCalculator):
    """
    Joe Friel Running Pace Zone Calculator (7 zones)
    
    Based on Joe Friel's "The Triathlete's Training Bible" methodology
    using lactate threshold pace as the foundation for zone calculation.
    """
    
    def calculate_zones(self, threshold_pace: Optional[float] = None,
                       race_distance_km: Optional[float] = None,
                       race_time_seconds: Optional[float] = None) -> PaceZoneResult:
        """
        Calculate Joe Friel pace zones from threshold pace or race time
        
        Args:
            threshold_pace: Lactate threshold pace in seconds per km
            race_distance_km: Recent race distance (5K or 10K preferred)
            race_time_seconds: Recent race time in seconds
        """
        if threshold_pace is None:
            if race_distance_km is None or race_time_seconds is None:
                raise InvalidParameterError("Either threshold_pace or race performance must be provided")
            
            # Estimate threshold pace from race performance
            race_pace = race_time_seconds / race_distance_km
            
            if race_distance_km <= 5.5:  # 5K race
                threshold_pace = race_pace * 1.03  # ~3% slower than 5K pace (more realistic)
            elif race_distance_km <= 10.5:  # 10K race  
                threshold_pace = race_pace * 1.01  # ~1% slower than 10K pace
            else:  # Longer races
                threshold_pace = race_pace * 0.98  # Slightly faster than longer race pace
                
            reference_time = (race_distance_km, race_time_seconds)
        else:
            reference_time = None
        
        zones = [
            self._create_zone(
                1, "Recovery", threshold_pace * 1.29, float('inf'),
                percentage_range=(129, None),
                description="Very easy pace for active recovery between harder sessions",
                purpose="Promote recovery while maintaining aerobic fitness",
                benefits=[
                    "Enhanced recovery between hard sessions",
                    "Improved circulation and waste removal",
                    "Maintenance of aerobic enzymes",
                    "Mental relaxation"
                ],
                duration="30-90 minutes",
                intensity="Very easy, no effort sensation",
                distances=["Recovery runs", "Easy shakeout runs"]
            ),
            self._create_zone(
                2, "Aerobic", threshold_pace * 1.14, threshold_pace * 1.29,
                percentage_range=(114, 129),
                description="Basic aerobic pace for building endurance base",
                purpose="Develop aerobic capacity and endurance foundation",
                benefits=[
                    "Improved oxygen delivery",
                    "Enhanced fat utilization",
                    "Increased mitochondrial density",
                    "Strengthened cardiac output"
                ],
                duration="45 minutes to several hours",
                intensity="Comfortable, conversational pace",
                distances=["Base building runs", "Long runs", "Easy distance"]
            ),
            self._create_zone(
                3, "Tempo", threshold_pace * 1.06, threshold_pace * 1.13,
                percentage_range=(106, 113),
                description="Moderately hard pace for tempo and rhythm development",
                purpose="Bridge between easy and threshold training",
                benefits=[
                    "Improved running economy",
                    "Enhanced lactate clearance preparation",
                    "Better pace judgment",
                    "Increased aerobic power"
                ],
                duration="20-60 minutes",
                intensity="Moderate effort, rhythmic breathing",
                distances=["Tempo runs", "Steady state runs", "Progression runs"]
            ),
            self._create_zone(
                4, "Sub-Threshold", threshold_pace * 1.01, threshold_pace * 1.05,
                percentage_range=(101, 105),
                description="Just below threshold pace preparation zone",
                purpose="Prepare for threshold training and racing",
                benefits=[
                    "Threshold preparation",
                    "Improved lactate tolerance",
                    "Enhanced race preparation",
                    "Mental toughness development"
                ],
                duration="15-40 minutes",
                intensity="Moderately hard, controlled breathing",
                distances=["Build-up runs", "Race preparation", "Strong tempo"]
            ),
            self._create_zone(
                5, "Super-Threshold", threshold_pace * 0.97, threshold_pace * 1.00,
                percentage_range=(97, 100),
                description="At or slightly faster than lactate threshold pace",
                purpose="Develop threshold power and lactate clearance",
                benefits=[
                    "Increased lactate threshold",
                    "Enhanced lactate clearance",
                    "Improved threshold endurance",
                    "Better 10K-Half marathon performance"
                ],
                duration="8-30 minutes in intervals",
                intensity="Hard, focused effort",
                distances=["Threshold intervals", "Lactate threshold pace", "10K-15K pace"]
            ),
            self._create_zone(
                6, "Aerobic Capacity", threshold_pace * 0.90, threshold_pace * 0.96,
                percentage_range=(90, 96),
                description="VO2max pace for aerobic power development",
                purpose="Improve maximum aerobic capacity and power",
                benefits=[
                    "Increased VO2max",
                    "Enhanced aerobic power",
                    "Improved oxygen utilization",
                    "Better 5K-10K performance"
                ],
                duration="3-8 minutes per interval",
                intensity="Hard to very hard effort",
                distances=["5K pace", "VO2max intervals", "3K-5K race pace"]
            ),
            self._create_zone(
                7, "Anaerobic Capacity", 0, threshold_pace * 0.90,
                percentage_range=(None, 90),
                description="Very fast pace for anaerobic power and speed development",
                purpose="Develop anaerobic capacity and neuromuscular power",
                benefits=[
                    "Enhanced anaerobic power",
                    "Improved neuromuscular recruitment",
                    "Increased stride frequency",
                    "Better sprint and speed endurance"
                ],
                duration="30 seconds to 3 minutes per interval",
                intensity="Very hard to maximum effort",
                distances=["Mile pace", "1500m pace", "Speed intervals"]
            )
        ]
        
        return PaceZoneResult(
            method=PaceZoneMethod.JOE_FRIEL,
            method_name="Joe Friel Running (7 zones)",
            threshold_pace=threshold_pace,
            reference_time=reference_time,
            zones=zones,
            method_description=(
                "Joe Friel's 7-zone system for runners is based on lactate threshold pace "
                "and provides comprehensive training intensity distribution. The system "
                "emphasizes aerobic base development in zones 1-3, threshold work in "
                "zones 4-5, and high-intensity training in zones 6-7."
            ),
            recommendations=[
                "Spend 80% of training time in zones 1-3 for aerobic development",
                "Zone 4 serves as preparation for harder threshold sessions",
                "Limit zone 5 threshold work to 1-2 sessions per week",
                "Use zones 6-7 sparingly and with adequate recovery",
                "Adjust zones seasonally based on current fitness testing",
                "Allow 48-72 hours recovery between high-intensity sessions"
            ]
        )


class PZICalculator(PaceZoneCalculator):
    """
    Pace Zone Index (PZI) Calculator (10 zones)
    
    Based on TrainingPeaks' comprehensive 10-zone system developed with
    Matt Fitzgerald. Uses 3K, 5K, or 10K performance to determine PZI level
    and corresponding training zones.
    """
    
    def calculate_zones(self, race_distance_km: float, race_time_seconds: float) -> PaceZoneResult:
        """
        Calculate PZI zones from recent race performance
        
        Args:
            race_distance_km: Race distance (3K, 5K, or 10K preferred)
            race_time_seconds: Race time in seconds
        """
        if race_distance_km not in [3.0, 5.0, 10.0]:
            logger.warning(f"PZI is optimized for 3K, 5K, or 10K races. Using {race_distance_km}K may be less accurate.")
        
        # Convert race performance to equivalent 5K pace for PZI calculation
        race_pace = race_time_seconds / race_distance_km
        
        # Adjust to 5K equivalent pace
        if race_distance_km == 3.0:
            equivalent_5k_pace = race_pace * 1.02  # 3K is ~2% faster than 5K
        elif race_distance_km == 10.0:
            equivalent_5k_pace = race_pace * 0.97  # 10K is ~3% slower than 5K
        else:
            equivalent_5k_pace = race_pace
        
        # Calculate training zones based on 5K pace
        # PZI zones are calculated as percentages of 5K pace
        
        zones = [
            self._create_zone(
                1, "Gray Zone 1", equivalent_5k_pace * 2.0, float('inf'),
                description="Too slow to qualify as exercise - walking pace",
                purpose="Not recommended for training - too slow for adaptation",
                benefits=["Minimal training benefit"],
                duration="Not recommended for training",
                intensity="Walking pace, no training effect",
                distances=["Walking", "Extremely easy recovery"]
            ),
            self._create_zone(
                2, "Low Aerobic", equivalent_5k_pace * 1.55, equivalent_5k_pace * 1.85,
                description="Recovery and base building pace",
                purpose="Promote recovery and basic aerobic development",
                benefits=[
                    "Enhanced recovery",
                    "Fat metabolism development",
                    "Basic aerobic enzyme adaptation",
                    "Active restoration"
                ],
                duration="30-120 minutes",
                intensity="Very easy, conversational",
                distances=["Recovery runs", "Easy base runs"]
            ),
            self._create_zone(
                3, "Moderate Aerobic", equivalent_5k_pace * 1.40, equivalent_5k_pace * 1.55,
                description="Foundation aerobic training pace",
                purpose="Build aerobic base and endurance capacity",
                benefits=[
                    "Improved oxygen delivery",
                    "Enhanced mitochondrial density",
                    "Increased cardiac output",
                    "Fundamental endurance development"
                ],
                duration="45-180 minutes",
                intensity="Comfortable, sustainable pace",
                distances=["Base building", "Long runs", "Aerobic development"]
            ),
            self._create_zone(
                4, "High Aerobic", equivalent_5k_pace * 1.15, equivalent_5k_pace * 1.40,
                description="Marathon to half-marathon pace range",
                purpose="Develop sustained aerobic power and racing endurance",
                benefits=[
                    "Enhanced running economy",
                    "Improved aerobic efficiency",
                    "Marathon/half-marathon preparation",
                    "Sustained pace development"
                ],
                duration="30-120 minutes",
                intensity="Moderate effort, controlled",
                distances=["Marathon pace", "Half-marathon pace", "Aerobic tempo"]
            ),
            self._create_zone(
                5, "Gray Zone 2", equivalent_5k_pace * 1.05, equivalent_5k_pace * 1.15,
                description="Between marathon pace and threshold - avoid for sustained work",
                purpose="Transition zone - not optimal for specific adaptations",
                benefits=["Limited training benefit in this range"],
                duration="Avoid sustained efforts here",
                intensity="Moderately hard but not threshold",
                distances=["Avoid training in this zone"]
            ),
            self._create_zone(
                6, "Threshold", equivalent_5k_pace * 0.95, equivalent_5k_pace * 1.05,
                description="Lactate threshold pace - comfortably hard effort",
                purpose="Develop lactate clearance and threshold power",
                benefits=[
                    "Increased lactate threshold",
                    "Enhanced lactate clearance",
                    "Improved threshold endurance",
                    "Better 10K-15K performance"
                ],
                duration="20-60 minutes total",
                intensity="Comfortably hard, controlled breathing",
                distances=["Tempo runs", "Threshold intervals", "15K-10 mile pace"]
            ),
            self._create_zone(
                7, "Gray Zone 3", equivalent_5k_pace * 0.88, equivalent_5k_pace * 0.95,
                description="Between threshold and VO2max - too fast for tempo, too slow for intervals",
                purpose="Transition zone - not optimal for training adaptations",
                benefits=["Limited specific training benefit"],
                duration="Avoid sustained training here",
                intensity="Hard but not maximally beneficial",
                distances=["Avoid training in this zone"]
            ),
            self._create_zone(
                8, "VO2max", equivalent_5k_pace * 0.83, equivalent_5k_pace * 0.88,
                description="VO2max pace for aerobic power development",
                purpose="Maximize aerobic capacity and VO2max",
                benefits=[
                    "Increased VO2max",
                    "Enhanced aerobic power",
                    "Improved oxygen utilization",
                    "Better 3K-5K performance"
                ],
                duration="3-8 minutes per interval",
                intensity="Hard, rhythmic breathing",
                distances=["5K pace", "3K-5K race pace", "VO2max intervals"]
            ),
            self._create_zone(
                9, "Gray Zone 4", equivalent_5k_pace * 0.78, equivalent_5k_pace * 0.83,
                description="Slightly faster than VO2max pace - less efficient for VO2max development",
                purpose="Too fast for VO2max work, too slow for pure speed",
                benefits=["Reduced training efficiency in this zone"],
                duration="Avoid sustained training here",
                intensity="Very hard but not optimally beneficial",
                distances=["Avoid extended training in this zone"]
            ),
            self._create_zone(
                10, "Speed", 180, equivalent_5k_pace * 0.78,  # Approximately 3:00/km minimum
                description="Pure speed development - mile pace to sprint pace",
                purpose="Develop maximum speed and neuromuscular power",
                benefits=[
                    "Enhanced neuromuscular power",
                    "Improved running mechanics",
                    "Increased stride efficiency",
                    "Better sprint capacity"
                ],
                duration="30 seconds to 8 minutes with recovery",
                intensity="Fast to maximum effort",
                distances=["Mile pace", "1500m pace", "Speed development"]
            )
        ]
        
        return PaceZoneResult(
            method=PaceZoneMethod.PZI,
            method_name="Pace Zone Index (PZI) - 10 zones",
            threshold_pace=equivalent_5k_pace * 0.95,  # Approximate threshold from 5K pace
            reference_time=(race_distance_km, race_time_seconds),
            zones=zones,
            method_description=(
                "The Pace Zone Index (PZI) is TrainingPeaks' comprehensive 10-zone system "
                "that identifies both optimal training zones (2, 3, 4, 6, 8, 10) and "
                "'gray zones' (1, 5, 7, 9) that should be avoided for sustained training. "
                "This system is designed to maximize training efficiency by focusing on "
                "physiologically optimal pace ranges."
            ),
            recommendations=[
                "Focus training on zones 2, 3, 4, 6, 8, and 10 - avoid gray zones",
                "Use zones 2-4 for 80% of training volume (aerobic development)",
                "Zone 6 for tempo and threshold training 1-2x per week",
                "Zone 8 for VO2max intervals with adequate recovery",
                "Zone 10 for speed work and neuromuscular development",
                "Avoid sustained efforts in gray zones 1, 5, 7, and 9",
                "Adjust paces based on environmental conditions and fatigue"
            ]
        )


class USATCalculator(PaceZoneCalculator):
    """
    USA Triathlon (USAT) Running Pace Zone Calculator (6 zones)
    
    Based on USA Triathlon coaching methodology using threshold pace
    or 5K race performance to determine training zones.
    """
    
    def calculate_zones(self, threshold_pace: Optional[float] = None,
                       race_5k_time_seconds: Optional[float] = None) -> PaceZoneResult:
        """
        Calculate USAT pace zones from threshold pace or 5K time
        
        Args:
            threshold_pace: Threshold pace in seconds per km
            race_5k_time_seconds: Recent 5K race time in seconds
        """
        if threshold_pace is None and race_5k_time_seconds is None:
            raise InvalidParameterError("Either threshold_pace or race_5k_time_seconds must be provided")
        
        if threshold_pace is None:
            # Calculate threshold pace from 5K time (approximately 3% slower than 5K pace)
            race_5k_pace = race_5k_time_seconds / 5.0
            threshold_pace = race_5k_pace * 1.03
            reference_time = (5.0, race_5k_time_seconds)
        else:
            reference_time = None
        
        zones = [
            self._create_zone(
                1, "Recovery", threshold_pace * 1.25, threshold_pace * 1.40,
                percentage_range=(125, 140),
                description="Active recovery pace for easy regeneration runs",
                purpose="Promote active recovery and maintain aerobic base",
                benefits=[
                    "Enhanced recovery between hard sessions",
                    "Improved blood flow and waste removal",
                    "Maintenance of aerobic fitness",
                    "Mental refreshment"
                ],
                duration="20-60 minutes",
                intensity="Very easy, effortless feeling",
                distances=["Recovery runs", "Easy shakeout runs"]
            ),
            self._create_zone(
                2, "Aerobic Base", threshold_pace * 1.15, threshold_pace * 1.25,
                percentage_range=(115, 125),
                description="Fundamental aerobic development pace",
                purpose="Build aerobic capacity and endurance foundation",
                benefits=[
                    "Improved cardiovascular efficiency",
                    "Enhanced fat utilization",
                    "Increased mitochondrial density",
                    "Strengthened aerobic enzymes"
                ],
                duration="45 minutes to 3+ hours",
                intensity="Comfortable, conversational pace",
                distances=["Base runs", "Long runs", "Easy distance"]
            ),
            self._create_zone(
                3, "Aerobic Development", threshold_pace * 1.05, threshold_pace * 1.15,
                percentage_range=(105, 115),
                description="Moderate aerobic pace for building aerobic power",
                purpose="Bridge between easy running and threshold work",
                benefits=[
                    "Enhanced aerobic power",
                    "Improved running economy",
                    "Better pace judgment",
                    "Increased sustainable pace"
                ],
                duration="30-90 minutes",
                intensity="Moderate effort, controlled breathing",
                distances=["Steady runs", "Progressive runs", "Moderate tempo"]
            ),
            self._create_zone(
                4, "Lactate Threshold", threshold_pace * 0.98, threshold_pace * 1.02,
                percentage_range=(98, 102),
                description="Comfortably hard pace at lactate threshold",
                purpose="Develop lactate clearance and threshold endurance",
                benefits=[
                    "Increased lactate threshold pace",
                    "Enhanced lactate buffering",
                    "Improved threshold endurance",
                    "Better 10K-15K race performance"
                ],
                duration="20-60 minutes total in intervals",
                intensity="Comfortably hard, focused effort",
                distances=["Tempo runs", "Threshold intervals", "10K-15K pace"]
            ),
            self._create_zone(
                5, "VO2max", threshold_pace * 0.90, threshold_pace * 0.96,
                percentage_range=(90, 96),
                description="High intensity pace for maximum aerobic development",
                purpose="Maximize aerobic capacity and VO2max",
                benefits=[
                    "Increased VO2max",
                    "Enhanced aerobic power",
                    "Improved oxygen utilization efficiency",
                    "Better 3K-5K race performance"
                ],
                duration="3-8 minutes per interval",
                intensity="Hard effort, deep rhythmic breathing",
                distances=["5K pace", "3K-5K race pace", "VO2max intervals"]
            ),
            self._create_zone(
                6, "Neuromuscular Power", threshold_pace * 0.75, threshold_pace * 0.90,
                percentage_range=(75, 90),
                description="Very fast pace for speed and power development",
                purpose="Develop anaerobic capacity and neuromuscular power",
                benefits=[
                    "Enhanced anaerobic power",
                    "Improved neuromuscular coordination",
                    "Increased stride efficiency",
                    "Better sprint and speed endurance"
                ],
                duration="30 seconds to 5 minutes per interval",
                intensity="Very hard to maximum effort",
                distances=["Mile pace", "1500m pace", "Speed intervals"]
            )
        ]
        
        return PaceZoneResult(
            method=PaceZoneMethod.USAT_RUNNING,
            method_name="USAT Running (6 zones)",
            threshold_pace=threshold_pace,
            reference_time=reference_time,
            zones=zones,
            method_description=(
                "USA Triathlon's 6-zone system provides a comprehensive approach to "
                "running training intensity distribution. Based on lactate threshold pace, "
                "this system emphasizes balanced development across all energy systems "
                "while maintaining the aerobic foundation essential for endurance performance."
            ),
            recommendations=[
                "Spend 70-80% of training time in zones 1-3 for aerobic development",
                "Zone 4 threshold work should be limited to 1-2 sessions per week",
                "Use zone 5 VO2max work sparingly with full recovery between sessions",
                "Zone 6 speed work for neuromuscular development and race preparation",
                "Periodize intensity distribution based on training phase and goals",
                "Monitor recovery and adjust zones based on current fitness level"
            ]
        )


class EightyTwentyCalculator(PaceZoneCalculator):
    """
    80/20 Running Pace Zone Calculator (7 zones)
    
    Based on Matt Fitzgerald's polarized training approach where 80% of
    training is done at low intensity and 20% at high intensity, with
    minimal time in moderate intensities.
    """
    
    def calculate_zones(self, threshold_pace: Optional[float] = None,
                       race_distance_km: Optional[float] = None,
                       race_time_seconds: Optional[float] = None) -> PaceZoneResult:
        """
        Calculate 80/20 pace zones from threshold pace or race performance
        
        Args:
            threshold_pace: Lactate threshold pace in seconds per km  
            race_distance_km: Recent race distance (5K-10K preferred)
            race_time_seconds: Recent race time in seconds
        """
        if threshold_pace is None:
            if race_distance_km is None or race_time_seconds is None:
                raise InvalidParameterError("Either threshold_pace or race performance must be provided")
            
            race_pace = race_time_seconds / race_distance_km
            
            # Estimate threshold pace from race performance
            if race_distance_km <= 5.5:  # 5K
                threshold_pace = race_pace * 1.03  # ~3% slower than 5K pace
            elif race_distance_km <= 10.5:  # 10K
                threshold_pace = race_pace * 1.01  # ~1% slower than 10K pace
            else:  # Longer races
                threshold_pace = race_pace * 0.98
                
            reference_time = (race_distance_km, race_time_seconds)
        else:
            reference_time = None
        
        zones = [
            self._create_zone(
                1, "Low Aerobic", threshold_pace * 1.25, float('inf'),
                percentage_range=(125, None),
                description="Very easy pace for recovery and aerobic base development",
                purpose="Active recovery and low-intensity aerobic development",
                benefits=[
                    "Enhanced recovery",
                    "Improved fat oxidation",
                    "Aerobic base maintenance",
                    "Stress reduction"
                ],
                duration="30-120 minutes",
                intensity="Very easy, no sense of effort",
                distances=["Recovery runs", "Easy base runs"]
            ),
            self._create_zone(
                2, "Moderate Aerobic", threshold_pace * 1.09, threshold_pace * 1.25,
                percentage_range=(109, 125),
                description="Comfortable aerobic pace for base building",
                purpose="Primary aerobic development and endurance building",
                benefits=[
                    "Improved cardiovascular efficiency",
                    "Enhanced mitochondrial density",
                    "Better fat utilization",
                    "Fundamental fitness development"
                ],
                duration="45 minutes to several hours",
                intensity="Comfortable, conversational pace",
                distances=["Base runs", "Long runs", "Aerobic development"]
            ),
            self._create_zone(
                "X", "Avoid Zone X", threshold_pace * 1.02, threshold_pace * 1.09,
                percentage_range=(102, 109),
                description="Moderate intensity zone to avoid in polarized training",
                purpose="Gray zone - not recommended for sustained training",
                benefits=["Minimal training benefit - avoid this zone"],
                duration="Minimize time spent here",
                intensity="Moderate but not beneficial",
                distances=["Avoid training in this zone"]
            ),
            self._create_zone(
                3, "Threshold", threshold_pace * 0.97, threshold_pace * 1.02,
                percentage_range=(97, 102),
                description="Lactate threshold pace for threshold development",
                purpose="Develop lactate clearance and threshold power",
                benefits=[
                    "Increased lactate threshold",
                    "Enhanced lactate buffering capacity",
                    "Improved threshold endurance",
                    "Better race-pace sustainability"
                ],
                duration="20-40 minutes total per session",
                intensity="Comfortably hard, controlled effort",
                distances=["Tempo runs", "Threshold intervals", "Time trial pace"]
            ),
            self._create_zone(
                "Y", "Avoid Zone Y", threshold_pace * 0.92, threshold_pace * 0.97,
                percentage_range=(92, 97),
                description="Above threshold zone to minimize in polarized training",
                purpose="Gray zone - limit time spent here",
                benefits=["Limited benefit - use sparingly"],
                duration="Minimize time in this zone",
                intensity="Hard but not optimally beneficial",
                distances=["Transition through this zone quickly"]
            ),
            self._create_zone(
                4, "VO2max", threshold_pace * 0.85, threshold_pace * 0.92,
                percentage_range=(85, 92),
                description="VO2max pace for aerobic power development",
                purpose="Maximize aerobic capacity and VO2max",
                benefits=[
                    "Increased VO2max",
                    "Enhanced aerobic power",
                    "Improved oxygen utilization",
                    "Better 3K-5K performance"
                ],
                duration="3-8 minutes per interval",
                intensity="Hard, deep breathing",
                distances=["5K pace", "VO2max intervals", "Track intervals"]
            ),
            self._create_zone(
                5, "Speed", threshold_pace * 0.70, threshold_pace * 0.85,
                percentage_range=(70, 85),
                description="High speed pace for neuromuscular development",
                purpose="Develop speed and neuromuscular power",
                benefits=[
                    "Enhanced neuromuscular power",
                    "Improved running mechanics",
                    "Increased stride efficiency",
                    "Better sprint capacity"
                ],
                duration="30 seconds to 5 minutes per interval",
                intensity="Very hard to maximum effort",
                distances=["Mile pace", "Speed intervals", "Strides"]
            )
        ]
        
        return PaceZoneResult(
            method=PaceZoneMethod.EIGHTY_TWENTY_RUNNING,
            method_name="80/20 Running (7 zones)",
            threshold_pace=threshold_pace,
            reference_time=reference_time,
            zones=zones,
            method_description=(
                "Matt Fitzgerald's 80/20 polarized training system emphasizes spending "
                "80% of training time at low intensity (zones 1-2) and 20% at high "
                "intensity (zones 3-5), while avoiding or minimizing time in moderate "
                "intensity gray zones (X and Y). This approach optimizes training "
                "efficiency and reduces injury risk."
            ),
            recommendations=[
                "Spend 80% of training time in zones 1-2 at low intensity",
                "Allocate 20% of training time to zones 3-5 at high intensity",
                "Minimize time in gray zones X and Y - pass through quickly",
                "Zone 3 threshold work 1-2 times per week maximum",
                "Zone 4 VO2max work with adequate recovery between sessions",
                "Zone 5 speed work for race preparation and neuromuscular development",
                "Maintain strict intensity discipline to preserve polarized distribution"
            ]
        )


class PaceZoneAnalyzer(FitnessAnalyzer):
    """
    Main pace zone analyzer implementing the interface
    """
    
    def __init__(self):
        self.calculators = {
            PaceZoneMethod.JACK_DANIELS: JackDanielsCalculator(),
            PaceZoneMethod.JOE_FRIEL: JoeFrielCalculator(),
            PaceZoneMethod.PZI: PZICalculator(),
            PaceZoneMethod.USAT_RUNNING: USATCalculator(),
            PaceZoneMethod.EIGHTY_TWENTY_RUNNING: EightyTwentyCalculator(),
        }
    
    def analyze(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """
        Analyze pace zones based on filter criteria
        This is a placeholder - in practice, you'd extract race data from the database
        """
        # This would typically extract recent race performances from the database
        # For now, return a sample result
        logger.info(f"Analyzing pace zones for user {filter_criteria.user_id}")
        
        return AnalyticsResult(
            analytics_type=AnalyticsType.PACE_ANALYSIS,
            data={
                "message": "Pace zone analysis requires specific race performance data",
                "available_methods": [method.value for method in PaceZoneMethod],
                "usage": "Use calculate_pace_zones() method with specific parameters"
            }
        )
    
    def calculate_pace_zones(self, method: PaceZoneMethod, **kwargs) -> PaceZoneResult:
        """
        Calculate pace zones using specified method and parameters
        
        Args:
            method: Pace zone calculation method
            **kwargs: Method-specific parameters such as:
                - vdot: VDOT value (Jack Daniels)
                - distance_km, time_seconds: Race performance (Jack Daniels, Joe Friel, 80/20)
                - threshold_pace: Threshold pace in sec/km (Joe Friel, USAT, 80/20)
                - race_distance_km, race_time_seconds: Race data (PZI)
                - race_5k_time_seconds: 5K time in seconds (USAT)
            
        Returns:
            PaceZoneResult with calculated zones
            
        Raises:
            InvalidParameterError: If method is unknown or required parameters missing
        """
        if method not in self.calculators:
            raise InvalidParameterError(f"Unknown pace zone method: {method}")
        
        calculator = self.calculators[method]
        try:
            return calculator.calculate_zones(**kwargs)
        except TypeError as e:
            # Convert TypeError from missing/invalid parameters to more helpful error
            raise InvalidParameterError(f"Invalid parameters for {method.value}: {str(e)}")
        except Exception as e:
            # Re-raise other exceptions as-is
            raise
    
    def compare_methods(self, reference_params: Dict[str, Any]) -> Dict[str, PaceZoneResult]:
        """
        Compare pace zones across different methods using the same reference
        
        Args:
            reference_params: Common parameters (e.g., race_distance_km, race_time_seconds)
            
        Returns:
            Dictionary mapping method names to their results
        """
        results = {}
        
        for method, calculator in self.calculators.items():
            try:
                # Adapt parameters for each method
                adapted_params = self._adapt_parameters(method, reference_params)
                result = calculator.calculate_zones(**adapted_params)
                results[method.value] = result
            except Exception as e:
                logger.warning(f"Failed to calculate {method.value} zones: {e}")
                continue
        
        return results
    
    def _adapt_parameters(self, method: PaceZoneMethod, params: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt parameters for specific method requirements"""
        adapted = params.copy()
        
        # Each calculator may have different parameter requirements
        if method == PaceZoneMethod.JACK_DANIELS:
            # Jack Daniels can use VDOT or race performance
            if 'vdot' in params:
                return {'vdot': params['vdot']}
            elif 'race_distance_km' in params and 'race_time_seconds' in params:
                return {
                    'distance_km': params['race_distance_km'],
                    'time_seconds': params['race_time_seconds']
                }
        
        elif method == PaceZoneMethod.JOE_FRIEL:
            # Joe Friel uses threshold pace or race performance
            if 'threshold_pace' in params:
                return {'threshold_pace': params['threshold_pace']}
            elif 'race_distance_km' in params and 'race_time_seconds' in params:
                return {
                    'race_distance_km': params['race_distance_km'],
                    'race_time_seconds': params['race_time_seconds']
                }
        
        elif method == PaceZoneMethod.PZI:
            # PZI requires race performance
            if 'race_distance_km' in params and 'race_time_seconds' in params:
                return {
                    'race_distance_km': params['race_distance_km'],
                    'race_time_seconds': params['race_time_seconds']
                }
        
        elif method == PaceZoneMethod.USAT_RUNNING:
            # USAT uses threshold pace or 5K time
            if 'threshold_pace' in params:
                return {'threshold_pace': params['threshold_pace']}
            elif 'race_5k_time_seconds' in params:
                return {'race_5k_time_seconds': params['race_5k_time_seconds']}
            elif params.get('race_distance_km') == 5.0 and 'race_time_seconds' in params:
                return {'race_5k_time_seconds': params['race_time_seconds']}
        
        elif method == PaceZoneMethod.EIGHTY_TWENTY_RUNNING:
            # 80/20 uses threshold pace or race performance
            if 'threshold_pace' in params:
                return {'threshold_pace': params['threshold_pace']}
            elif 'race_distance_km' in params and 'race_time_seconds' in params:
                return {
                    'race_distance_km': params['race_distance_km'],
                    'race_time_seconds': params['race_time_seconds']
                }
        
        return adapted

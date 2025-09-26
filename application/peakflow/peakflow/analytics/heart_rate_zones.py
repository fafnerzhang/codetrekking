#!/usr/bin/env python3
"""
Heart Rate Zones Analytics Module

This module provides comprehensive heart rate zone calculations based on various
maximum heart rate models including:
- BCF/ABCC/WCPP Revised (7 zones) - British Cycling Federation
- Peter Keen (4 zones) - Original British Cycling method  
- Ric Stern (7 zones) - Alternative 7-zone system
- Sally Edwards (5 zones) - Heart Zones methodology
- Timex (5 zones) - Traditional 5-zone system
- MyProCoach (5 zones) - Performance-based zones

Each method provides zone ranges with detailed explanations of training purposes
and physiological adaptations for user understanding.
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


class HeartRateZoneMethod(Enum):
    """Available heart rate zone calculation methods"""
    # Maximum HR based methods
    BCF_ABCC_WCPP_REVISED = "bcf_abcc_wcpp_revised"  # 7 zones
    PETER_KEEN = "peter_keen"  # 4 zones
    RIC_STERN = "ric_stern"  # 7 zones
    SALLY_EDWARDS = "sally_edwards"  # 5 zones
    TIMEX = "timex"  # 5 zones
    MYPROCOACH = "myprocoach"  # 5 zones
    
    # Lactate threshold based methods
    JOE_FRIEL = "joe_friel"  # 7 zones
    JOE_FRIEL_RUNNING = "joe_friel_running"  # 7 zones
    JOE_FRIEL_CYCLING = "joe_friel_cycling"  # 7 zones
    ANDY_COGGAN = "andy_coggan"  # 5 zones
    USAT_RUNNING = "usat_running"  # 6 zones
    EIGHTY_TWENTY_RUNNING = "80_20_running"  # 7 zones


@dataclass
class HeartRateZone:
    """Represents a single heart rate training zone"""
    zone_number: int
    zone_name: str
    percentage_range: Tuple[float, float]  # (min_percent, max_percent) of max HR
    heart_rate_range: Tuple[int, int]  # (min_hr, max_hr) in BPM
    description: str
    purpose: str
    training_benefits: List[str]
    duration_guidelines: str
    intensity_feel: str


@dataclass 
class HeartRateZoneResult:
    """Result containing heart rate zone calculations and analysis"""
    method: HeartRateZoneMethod
    method_name: str
    max_heart_rate: int
    age: Optional[int]
    zones: List[HeartRateZone]
    method_description: str
    recommendations: List[str]
    calculated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format"""
        return {
            'method': self.method.value,
            'method_name': self.method_name,
            'max_heart_rate': self.max_heart_rate,
            'age': self.age,
            'zones': [
                {
                    'zone_number': z.zone_number,
                    'zone_name': z.zone_name,
                    'percentage_range': z.percentage_range,
                    'heart_rate_range': z.heart_rate_range,
                    'description': z.description,
                    'purpose': z.purpose,
                    'training_benefits': z.training_benefits,
                    'duration_guidelines': z.duration_guidelines,
                    'intensity_feel': z.intensity_feel
                } for z in self.zones
            ],
            'method_description': self.method_description,
            'recommendations': self.recommendations,
            'calculated_at': self.calculated_at.isoformat()
        }


class HeartRateZoneCalculator(ABC):
    """Abstract base class for heart rate zone calculators"""

    @abstractmethod
    def calculate_zones(
        self,
        max_heart_rate: Optional[int] = None,
        resting_heart_rate: Optional[int] = None,
        lthr: Optional[int] = None,
        age: Optional[int] = None
    ) -> HeartRateZoneResult:
        """
        Calculate heart rate zones using provided parameters

        Args:
            max_heart_rate: Maximum heart rate in BPM
            resting_heart_rate: Resting heart rate in BPM
            lthr: Lactate threshold heart rate in BPM
            age: Age in years

        Returns:
            HeartRateZoneResult with calculated zones
        """
        pass
    
    @staticmethod
    def estimate_max_heart_rate(age: int, method: str = "tanaka") -> int:
        """
        Estimate maximum heart rate from age using various formulas
        
        Args:
            age: Age in years
            method: Formula to use ("fox", "tanaka", "gulati", "fairbarn")
            
        Returns:
            Estimated maximum heart rate in BPM
        """
        if method == "fox":
            # Classic Fox formula: 220 - age
            return 220 - age
        elif method == "tanaka":
            # Tanaka et al.: 208 - (0.7 × age) - more accurate for older adults
            return int(208 - (0.7 * age))
        elif method == "gulati":
            # Gulati formula for women: 206 - (0.88 × age)
            return int(206 - (0.88 * age))
        elif method == "fairbarn":
            # Fairbarn formula: 201 - (0.63 × age)
            return int(201 - (0.63 * age))
        else:
            # Default to Tanaka (most accurate for general population)
            return int(208 - (0.7 * age))
    
    def _calculate_hr_from_percentage(self, max_hr: int, percentage: float) -> int:
        """Calculate heart rate from percentage of maximum"""
        return int(max_hr * (percentage / 100))
    
    def _create_zone(self, zone_num: int, zone_name: str, min_pct: float, max_pct: float,
                    max_hr: int, description: str, purpose: str, benefits: List[str],
                    duration: str, intensity: str) -> HeartRateZone:
        """Helper method to create a heart rate zone"""
        min_hr = self._calculate_hr_from_percentage(max_hr, min_pct)
        max_hr_zone = self._calculate_hr_from_percentage(max_hr, max_pct)
        
        return HeartRateZone(
            zone_number=zone_num,
            zone_name=zone_name,
            percentage_range=(min_pct, max_pct),
            heart_rate_range=(min_hr, max_hr_zone),
            description=description,
            purpose=purpose,
            training_benefits=benefits,
            duration_guidelines=duration,
            intensity_feel=intensity
        )


class BCFABCCWCPPRevisedCalculator(HeartRateZoneCalculator):
    """
    BCF/ABCC/WCPP Revised (7 zones) Heart Rate Calculator
    
    Based on the British Cycling Federation, Association of British Cycling Coaches,
    and World Class Performance Programme methodology. This is the current standard
    used by British Cycling.
    """
    
    def calculate_zones(
        self,
        max_heart_rate: Optional[int] = None,
        resting_heart_rate: Optional[int] = None,
        lthr: Optional[int] = None,
        age: Optional[int] = None
    ) -> HeartRateZoneResult:
        """Calculate BCF/ABCC/WCPP Revised 7-zone system"""
        if max_heart_rate is None and age is None:
            raise InvalidParameterError("Either max_heart_rate or age must be provided")

        if max_heart_rate is None:
            max_heart_rate = self.estimate_max_heart_rate(age)
        zones = [
            self._create_zone(
                1, "Recovery", 0, 60, max_heart_rate,
                "Very light intensity, primarily for recovery rides",
                "Active recovery and restoration",
                ["Enhanced recovery", "Improved circulation", "Mental relaxation"],
                "30-90 minutes", "Very easy, can maintain conversation easily"
            ),
            self._create_zone(
                2, "Fat Burning", 60, 65, max_heart_rate,
                "Slightly more intense but still low end, aiming to improve fat metabolism",
                "Optimize fat burning and build aerobic base",
                ["Improved fat oxidation", "Enhanced metabolic efficiency", "Aerobic base development"],
                "45-120 minutes", "Easy, comfortable conversation possible"
            ),
            self._create_zone(
                3, "Basic Endurance", 65, 75, max_heart_rate,
                "Focus on building aerobic base endurance for cardiovascular and muscular development",
                "Build fundamental aerobic capacity and endurance",
                ["Increased stroke volume", "Improved oxygen delivery", "Enhanced capillarization"],
                "60-180 minutes", "Moderate, conversation possible with some effort"
            ),
            self._create_zone(
                4, "Aerobic Endurance", 75, 82, max_heart_rate,
                "Moderate intensity to improve oxygen transport and aerobic capacity",
                "Develop aerobic power and efficiency",
                ["Increased VO2max", "Improved lactate clearance", "Enhanced aerobic enzymes"],
                "30-90 minutes", "Moderately hard, conversation becomes difficult"
            ),
            self._create_zone(
                5, "Road Race", 82, 89, max_heart_rate,
                "Challenging intensity for race preparation and high-end endurance",
                "Prepare for competitive racing demands",
                ["Improved lactate threshold", "Enhanced race-pace endurance", "Mental toughness"],
                "20-60 minutes", "Hard, conversation very difficult"
            ),
            self._create_zone(
                6, "Speed Training", 89, 94, max_heart_rate,
                "High intensity to improve lactate threshold and speed endurance",
                "Develop speed and lactate tolerance",
                ["Increased lactate buffering", "Improved neuromuscular power", "Enhanced speed endurance"],
                "8-40 minutes in intervals", "Very hard, conversation impossible"
            ),
            self._create_zone(
                7, "Anaerobic Sprint", 94, 100, max_heart_rate,
                "Maximum intensity for anaerobic capacity and sprint power development",
                "Develop maximum power and anaerobic capacity",
                ["Enhanced anaerobic power", "Improved neuromuscular recruitment", "Sprint capability"],
                "30 seconds to 8 minutes in intervals", "Maximum effort, all-out intensity"
            )
        ]
        
        return HeartRateZoneResult(
            method=HeartRateZoneMethod.BCF_ABCC_WCPP_REVISED,
            method_name="BCF/ABCC/WCPP Revised (7 zones)",
            max_heart_rate=max_heart_rate,
            age=age,
            zones=zones,
            method_description=(
                "The BCF/ABCC/WCPP Revised method is the current standard used by British Cycling, "
                "the Association of British Cycling Coaches, and the World Class Performance Programme. "
                "This 7-zone system provides comprehensive training guidance from recovery to maximum "
                "anaerobic efforts, allowing precise training prescription for all aspects of cycling fitness."
            ),
            recommendations=[
                "Spend 80% of training time in zones 1-3 for aerobic base development",
                "Use zones 4-5 for tempo and threshold training 1-2x per week",
                "Limit zones 6-7 to 1-2 sessions per week with adequate recovery",
                "Ensure proper warm-up before high-intensity zones (5-7)",
                "Monitor recovery between high-intensity sessions"
            ]
        )


class PeterKeenCalculator(HeartRateZoneCalculator):
    """
    Peter Keen (4 zones) Heart Rate Calculator
    
    Original heart rate zones used by British Cycling, developed by Peter Keen.
    This is the system that preceded the current BCF/ABCC/WCPP Revised method
    and was used with Chris Boardman and other elite British cyclists.
    """
    
    def calculate_zones(
        self,
        max_heart_rate: Optional[int] = None,
        resting_heart_rate: Optional[int] = None,
        lthr: Optional[int] = None,
        age: Optional[int] = None
    ) -> HeartRateZoneResult:
        """Calculate Peter Keen 4-zone system"""
        if max_heart_rate is None and age is None:
            raise InvalidParameterError("Either max_heart_rate or age must be provided")

        if max_heart_rate is None:
            max_heart_rate = self.estimate_max_heart_rate(age)
        zones = [
            self._create_zone(
                1, "Active Recovery", 0, 77, max_heart_rate,
                "Very low intensity for active recovery and skill development",
                "Active recovery between harder training sessions",
                ["Enhanced recovery", "Improved basic skills", "Fat utilization", "Reduced stress"],
                "Several hours possible", "Very easy, unaware of breathing, continuous conversation"
            ),
            self._create_zone(
                2, "Aerobic Workout", 77, 82, max_heart_rate,
                "Fundamental aerobic training intensity for endurance development",
                "Build aerobic capacity and endurance base",
                ["Improved oxygen delivery", "Increased blood volume", "Enhanced fat metabolism", "Capillary development"],
                "1.5-2 hours daily", "Comfortable but requires concentration, conversation with pauses"
            ),
            self._create_zone(
                3, "Threshold Training", 85, 92, max_heart_rate,
                "Training at critical threshold for sustained power development",
                "Improve threshold power and lactate tolerance",
                ["Enhanced lactate clearance", "Improved threshold power", "Mental toughness", "Race preparation"],
                "25-30 minutes continuous", "Hard effort, rapid breathing, intense concentration required"
            ),
            self._create_zone(
                4, "Interval Training", 92, 100, max_heart_rate,
                "High-intensity intervals for maximum power and anaerobic development",
                "Develop maximum power and anaerobic capacity",
                ["Increased maximum power", "Enhanced anaerobic capacity", "Improved lactate tolerance", "Sprint development"],
                "30 seconds to 3 minutes with recovery", "Near maximum effort, conversation impossible"
            )
        ]
        
        return HeartRateZoneResult(
            method=HeartRateZoneMethod.PETER_KEEN,
            method_name="Peter Keen (4 zones)",
            max_heart_rate=max_heart_rate,
            age=age,
            zones=zones,
            method_description=(
                "The Peter Keen method is the original 4-zone system developed for British Cycling "
                "and used with elite athletes like Chris Boardman. This system focuses on four "
                "distinct training intensities with clear physiological purposes. It emphasizes "
                "the importance of Level 2 training as the foundation of cycling fitness."
            ),
            recommendations=[
                "Level 2 should form the basis of training - at least 3 sessions per week",
                "Level 1 is essential for recovery and skill development",
                "Level 3 training twice per week for threshold development",
                "Level 4 intervals should be added close to racing season",
                "Avoid group training that compromises intended training level"
            ]
        )


class RicSternCalculator(HeartRateZoneCalculator):
    """
    Ric Stern (7 zones) Heart Rate Calculator
    
    Alternative 7-zone system developed by Ric Stern, providing detailed
    training zones for comprehensive fitness development.
    """
    
    def calculate_zones(
        self,
        max_heart_rate: Optional[int] = None,
        resting_heart_rate: Optional[int] = None,
        lthr: Optional[int] = None,
        age: Optional[int] = None
    ) -> HeartRateZoneResult:
        """Calculate Ric Stern 7-zone system"""
        if max_heart_rate is None and age is None:
            raise InvalidParameterError("Either max_heart_rate or age must be provided")

        if max_heart_rate is None:
            max_heart_rate = self.estimate_max_heart_rate(age)
        zones = [
            self._create_zone(
                1, "Active Recovery", 0, 68, max_heart_rate,
                "Very light activity for recovery and restoration",
                "Promote recovery and maintain fitness",
                ["Enhanced recovery", "Improved circulation", "Stress reduction"],
                "30-90 minutes", "Very easy, no effort sensation"
            ),
            self._create_zone(
                2, "Extensive Endurance", 68, 78, max_heart_rate,
                "Basic aerobic endurance training foundation",
                "Build aerobic base and improve fat utilization",
                ["Improved aerobic enzymes", "Enhanced fat oxidation", "Increased mitochondrial density"],
                "1-5 hours", "Easy, comfortable conversation possible"
            ),
            self._create_zone(
                3, "Intensive Endurance", 78, 87, max_heart_rate,
                "Higher aerobic intensity for improved efficiency",
                "Develop aerobic power and efficiency",
                ["Increased lactate clearance", "Improved cardiac output", "Enhanced oxygen utilization"],
                "45-150 minutes", "Moderate, some concentration required"
            ),
            self._create_zone(
                4, "Sub-Threshold", 87, 93, max_heart_rate,
                "High aerobic intensity approaching threshold",
                "Prepare for threshold training and racing",
                ["Improved lactate tolerance", "Enhanced threshold preparation", "Mental preparation"],
                "20-60 minutes", "Moderately hard, conversation difficult"
            ),
            self._create_zone(
                5, "Threshold", 93, 99, max_heart_rate,
                "Training at or near lactate/functional threshold",
                "Develop threshold power and lactate clearance",
                ["Increased threshold power", "Enhanced lactate buffering", "Improved time trial performance"],
                "8-40 minutes", "Hard, focused breathing pattern"
            ),
            self._create_zone(
                6, "Anaerobic", 99, 102, max_heart_rate,
                "Supra-threshold training for anaerobic development",
                "Develop anaerobic capacity and power",
                ["Enhanced anaerobic power", "Improved lactate tolerance", "Increased maximum power"],
                "30 seconds to 8 minutes", "Very hard, conversation impossible"
            ),
            self._create_zone(
                7, "Alactic Power", 102, 110, max_heart_rate,
                "Maximum power training for neuromuscular development",
                "Develop maximum sprint power and neural recruitment",
                ["Enhanced neuromuscular power", "Improved sprint capacity", "Maximum power development"],
                "5-15 seconds", "Maximum effort, all-out sprint"
            )
        ]
        
        return HeartRateZoneResult(
            method=HeartRateZoneMethod.RIC_STERN,
            method_name="Ric Stern (7 zones)",
            max_heart_rate=max_heart_rate,
            age=age,
            zones=zones,
            method_description=(
                "The Ric Stern 7-zone system provides a comprehensive approach to training "
                "intensity distribution. It offers detailed progression from recovery through "
                "maximum power development, with clear physiological targets for each zone."
            ),
            recommendations=[
                "Focus majority of training in zones 1-3 for aerobic development",
                "Use zone 4 as preparation for threshold training",
                "Zone 5 threshold training 1-2x per week maximum",
                "Limit zones 6-7 to specific training blocks",
                "Ensure adequate recovery between high-intensity sessions"
            ]
        )


class SallyEdwardsCalculator(HeartRateZoneCalculator):
    """
    Sally Edwards (5 zones) Heart Rate Calculator
    
    Heart Zones methodology developed by Sally Edwards, focusing on
    practical training zones for fitness and performance.
    """
    
    def calculate_zones(
        self,
        max_heart_rate: Optional[int] = None,
        resting_heart_rate: Optional[int] = None,
        lthr: Optional[int] = None,
        age: Optional[int] = None
    ) -> HeartRateZoneResult:
        """Calculate Sally Edwards 5-zone system"""
        if max_heart_rate is None and age is None:
            raise InvalidParameterError("Either max_heart_rate or age must be provided")

        if max_heart_rate is None:
            max_heart_rate = self.estimate_max_heart_rate(age)
        zones = [
            self._create_zone(
                1, "Healthy Heart", 50, 60, max_heart_rate,
                "Basic fitness and health maintenance zone",
                "Improve basic health and begin fitness development",
                ["Basic cardiovascular health", "Stress reduction", "Fat burning initiation"],
                "30-60 minutes", "Very comfortable, easy conversation"
            ),
            self._create_zone(
                2, "Temperate", 60, 70, max_heart_rate,
                "Comfortable aerobic training for base fitness",
                "Build aerobic base and improve fat metabolism",
                ["Enhanced fat oxidation", "Improved aerobic efficiency", "Basic endurance"],
                "45-90 minutes", "Comfortable, conversation easily maintained"
            ),
            self._create_zone(
                3, "Aerobic", 70, 80, max_heart_rate,
                "Core aerobic training zone for fitness development",
                "Develop aerobic capacity and endurance",
                ["Increased VO2max", "Improved cardiac efficiency", "Enhanced oxygen delivery"],
                "30-90 minutes", "Moderate effort, conversation requires some focus"
            ),
            self._create_zone(
                4, "Threshold", 80, 90, max_heart_rate,
                "High-intensity aerobic training approaching anaerobic threshold",
                "Improve lactate threshold and high-end aerobic power",
                ["Enhanced lactate clearance", "Improved threshold power", "Better race preparation"],
                "15-60 minutes", "Hard effort, conversation difficult"
            ),
            self._create_zone(
                5, "Red Line", 90, 100, max_heart_rate,
                "Maximum intensity training for peak performance",
                "Develop maximum power and anaerobic capacity",
                ["Maximum power development", "Enhanced anaerobic capacity", "Peak performance"],
                "30 seconds to 15 minutes", "Very hard to maximum effort"
            )
        ]
        
        return HeartRateZoneResult(
            method=HeartRateZoneMethod.SALLY_EDWARDS,
            method_name="Sally Edwards (5 zones)",
            max_heart_rate=max_heart_rate,
            age=age,
            zones=zones,
            method_description=(
                "The Sally Edwards Heart Zones method provides a practical 5-zone system "
                "designed for both fitness enthusiasts and competitive athletes. It emphasizes "
                "progressive training intensity with clear guidelines for each zone's purpose."
            ),
            recommendations=[
                "Beginners should focus on zones 1-2 for 4-6 weeks",
                "Zone 3 should form the base of most training programs",
                "Zone 4 training 1-2x per week for performance improvement",
                "Zone 5 training only for specific performance goals",
                "Monitor recovery and adjust intensity based on response"
            ]
        )


class TimexCalculator(HeartRateZoneCalculator):
    """
    Timex (5 zones) Heart Rate Calculator
    
    Traditional 5-zone system commonly used in fitness applications
    and heart rate monitors.
    """
    
    def calculate_zones(
        self,
        max_heart_rate: Optional[int] = None,
        resting_heart_rate: Optional[int] = None,
        lthr: Optional[int] = None,
        age: Optional[int] = None
    ) -> HeartRateZoneResult:
        """Calculate Timex 5-zone system"""
        if max_heart_rate is None and age is None:
            raise InvalidParameterError("Either max_heart_rate or age must be provided")

        if max_heart_rate is None:
            max_heart_rate = self.estimate_max_heart_rate(age)
        zones = [
            self._create_zone(
                1, "Warm-up", 50, 60, max_heart_rate,
                "Light activity for warm-up and recovery",
                "Prepare for exercise and aid recovery",
                ["Improved circulation", "Enhanced flexibility", "Stress relief"],
                "5-15 minutes for warm-up, 30-60 for recovery", "Very light, minimal effort"
            ),
            self._create_zone(
                2, "Fat Burn", 60, 70, max_heart_rate,
                "Optimal zone for fat burning and base fitness",
                "Maximize fat utilization and build aerobic base",
                ["Enhanced fat oxidation", "Improved metabolic efficiency", "Weight management"],
                "30-90 minutes", "Comfortable, easy conversation"
            ),
            self._create_zone(
                3, "Aerobic", 70, 80, max_heart_rate,
                "Cardiovascular fitness and endurance development",
                "Improve cardiovascular fitness and endurance",
                ["Increased heart efficiency", "Improved oxygen utilization", "Enhanced endurance"],
                "20-60 minutes", "Moderate, conversation with some effort"
            ),
            self._create_zone(
                4, "Anaerobic", 80, 90, max_heart_rate,
                "High-intensity training for performance improvement",
                "Develop lactate threshold and anaerobic power",
                ["Improved lactate tolerance", "Enhanced anaerobic capacity", "Performance gains"],
                "10-40 minutes in intervals", "Hard, conversation difficult"
            ),
            self._create_zone(
                5, "VO2 Max", 90, 100, max_heart_rate,
                "Maximum intensity for peak fitness development",
                "Develop maximum aerobic and anaerobic capacity",
                ["Maximum oxygen uptake", "Peak power development", "Elite performance"],
                "1-10 minutes in intervals", "Very hard to maximum effort"
            )
        ]
        
        return HeartRateZoneResult(
            method=HeartRateZoneMethod.TIMEX,
            method_name="Timex (5 zones)",
            max_heart_rate=max_heart_rate,
            age=age,
            zones=zones,
            method_description=(
                "The Timex 5-zone system is a traditional and widely-used heart rate training "
                "method. It provides clear, practical zones suitable for general fitness, "
                "weight management, and performance improvement."
            ),
            recommendations=[
                "Beginners should start with zones 1-2 for several weeks",
                "Zone 2 is optimal for weight loss and fat burning",
                "Zone 3 provides the best cardiovascular fitness benefits",
                "Zones 4-5 should be used sparingly with adequate recovery",
                "Always include warm-up and cool-down periods"
            ]
        )


class MyProCoachCalculator(HeartRateZoneCalculator):
    """
    MyProCoach (5 zones) Heart Rate Calculator
    
    Performance-based 5-zone system based on maximum heart rate
    percentages for structured training.
    """
    
    def calculate_zones(
        self,
        max_heart_rate: Optional[int] = None,
        resting_heart_rate: Optional[int] = None,
        lthr: Optional[int] = None,
        age: Optional[int] = None
    ) -> HeartRateZoneResult:
        """Calculate MyProCoach 5-zone system"""
        if max_heart_rate is None and age is None:
            raise InvalidParameterError("Either max_heart_rate or age must be provided")

        if max_heart_rate is None:
            max_heart_rate = self.estimate_max_heart_rate(age)
        zones = [
            self._create_zone(
                1, "Recovery", 68, 73, max_heart_rate,
                "Active recovery and restoration training",
                "Enhance recovery and maintain basic fitness",
                ["Improved recovery", "Enhanced circulation", "Stress reduction"],
                "30-120 minutes", "Very easy, effortless conversation"
            ),
            self._create_zone(
                2, "Base Endurance", 73.5, 80, max_heart_rate,
                "Foundational aerobic training for endurance base",
                "Build aerobic capacity and endurance foundation",
                ["Enhanced aerobic enzymes", "Improved fat utilization", "Increased capillary density"],
                "60-240 minutes", "Easy, comfortable conversation"
            ),
            self._create_zone(
                3, "Tempo", 80.5, 87, max_heart_rate,
                "Sustained aerobic training for improved efficiency",
                "Develop aerobic power and training efficiency",
                ["Improved lactate clearance", "Enhanced cardiac output", "Better oxygen utilization"],
                "20-90 minutes", "Moderate, some concentration required"
            ),
            self._create_zone(
                4, "Threshold", 87.5, 93, max_heart_rate,
                "Lactate threshold training for performance improvement",
                "Develop threshold power and lactate tolerance",
                ["Increased threshold power", "Enhanced lactate buffering", "Improved time trial ability"],
                "10-60 minutes", "Hard, focused effort required"
            ),
            self._create_zone(
                5, "VO2 Max", 93.5, 100, max_heart_rate,
                "Maximum aerobic and anaerobic power development",
                "Develop maximum power and aerobic capacity",
                ["Increased VO2max", "Enhanced anaerobic power", "Peak performance development"],
                "30 seconds to 8 minutes", "Very hard to maximum effort"
            )
        ]
        
        return HeartRateZoneResult(
            method=HeartRateZoneMethod.MYPROCOACH,
            method_name="MyProCoach (5 zones)",
            max_heart_rate=max_heart_rate,
            age=age,
            zones=zones,
            method_description=(
                "The MyProCoach 5-zone system is designed for structured training with "
                "precise percentage ranges. It balances simplicity with effective training "
                "prescription for performance-oriented athletes."
            ),
            recommendations=[
                "80% of training should be in zones 1-2 for aerobic base",
                "Zone 3 tempo work 1-2x per week for efficiency",
                "Zone 4 threshold training once per week maximum",
                "Zone 5 intervals only during specific training phases",
                "Monitor training load and adjust intensity distribution"
            ]
        )


class LactateThresholdZoneCalculator(HeartRateZoneCalculator):
    """
    Abstract base class for lactate threshold-based heart rate zone calculators

    These calculators use Lactate Threshold Heart Rate (LTHR) as the reference
    point for zone calculation rather than maximum heart rate.
    """
    
    def _calculate_hr_from_lthr_percentage(self, lthr: int, percentage: float) -> int:
        """Calculate heart rate from percentage of lactate threshold heart rate"""
        return int(lthr * (percentage / 100))
    
    def _create_lthr_zone(self, zone_num: int, zone_name: str, min_pct: float, max_pct: float,
                         lthr: int, description: str, purpose: str, benefits: List[str],
                         duration: str, intensity: str) -> HeartRateZone:
        """Helper method to create a lactate threshold-based heart rate zone"""
        min_hr = self._calculate_hr_from_lthr_percentage(lthr, min_pct)
        max_hr_zone = self._calculate_hr_from_lthr_percentage(lthr, max_pct)
        
        return HeartRateZone(
            zone_number=zone_num,
            zone_name=zone_name,
            percentage_range=(min_pct, max_pct),
            heart_rate_range=(min_hr, max_hr_zone),
            description=description,
            purpose=purpose,
            training_benefits=benefits,
            duration_guidelines=duration,
            intensity_feel=intensity
        )


class JoeFrielCalculator(LactateThresholdZoneCalculator):
    """
    Joe Friel (7 zones) Heart Rate Calculator
    
    General heart rate zones from Joe Friel's Training Bible series,
    based on lactate threshold heart rate. This is the general method
    for activities without sport-specific zones.
    """
    
    def calculate_zones(
        self,
        max_heart_rate: Optional[int] = None,
        resting_heart_rate: Optional[int] = None,
        lthr: Optional[int] = None,
        age: Optional[int] = None
    ) -> HeartRateZoneResult:
        """Calculate Joe Friel general 7-zone system"""
        # Priority: LTHR > max_heart_rate + age estimation
        if lthr is None:
            if max_heart_rate is None and age is None:
                raise InvalidParameterError("Either lthr, max_heart_rate, or age must be provided")

            if max_heart_rate is None:
                max_heart_rate = self.estimate_max_heart_rate(age)

            # Estimate LTHR from max HR (typically 86% for Joe Friel)
            lthr = int(max_heart_rate * 0.86)
            logger.warning(f"Using estimated LTHR {lthr} from max HR {max_heart_rate}. For accurate zones, provide actual threshold HR.")

        # Estimate max HR from LTHR for reference (LTHR is typically 86% of max HR)
        if max_heart_rate is None:
            estimated_max_hr = int(lthr / 0.86)
        else:
            estimated_max_hr = max_heart_rate
        
        zones = [
            self._create_lthr_zone(
                1, "Recovery", 0, 85, lthr,
                "Active recovery and very light aerobic activity",
                "Promote recovery and maintain basic aerobic function",
                ["Enhanced recovery", "Improved circulation", "Stress reduction", "Fat utilization"],
                "30-90 minutes", "Very easy, comfortable conversation"
            ),
            self._create_lthr_zone(
                2, "Aerobic", 85, 89, lthr,
                "Fundamental aerobic base training intensity",
                "Build aerobic capacity and enhance fat metabolism",
                ["Improved aerobic enzymes", "Enhanced fat oxidation", "Increased capillary density"],
                "45-150 minutes", "Easy, conversation possible with minimal effort"
            ),
            self._create_lthr_zone(
                3, "Tempo", 90, 94, lthr,
                "Moderate aerobic intensity for endurance development",
                "Improve aerobic efficiency and lactate clearance",
                ["Enhanced lactate clearance", "Improved cardiac efficiency", "Better oxygen utilization"],
                "20-90 minutes", "Moderate, conversation requires focus"
            ),
            self._create_lthr_zone(
                4, "Lactate Threshold", 95, 99, lthr,
                "Training at or just below lactate threshold",
                "Develop threshold power and lactate tolerance",
                ["Increased threshold capacity", "Enhanced lactate buffering", "Improved time trial performance"],
                "8-40 minutes", "Hard, focused breathing required"
            ),
            self._create_lthr_zone(
                5, "VO2max (5a)", 100, 102, lthr,
                "High-intensity aerobic intervals",
                "Develop maximum aerobic power",
                ["Increased VO2max", "Enhanced aerobic power", "Improved lactate tolerance"],
                "3-8 minutes in intervals", "Very hard, near maximum sustainable"
            ),
            self._create_lthr_zone(
                6, "Anaerobic (5b)", 103, 106, lthr,
                "Anaerobic capacity and speed endurance training",
                "Develop anaerobic power and speed",
                ["Enhanced anaerobic capacity", "Improved speed endurance", "Better finishing capability"],
                "30 seconds to 3 minutes", "Extremely hard, unsustainable"
            ),
            self._create_lthr_zone(
                7, "Neuromuscular (5c)", 107, 120, lthr,
                "Maximum neuromuscular power development",
                "Develop sprint power and neuromuscular coordination",
                ["Enhanced neuromuscular power", "Improved sprint capability", "Maximum power development"],
                "5-15 seconds", "All-out sprint effort"
            )
        ]
        
        return HeartRateZoneResult(
            method=HeartRateZoneMethod.JOE_FRIEL,
            method_name="Joe Friel (7 zones)",
            max_heart_rate=estimated_max_hr,
            age=age,
            zones=zones,
            method_description=(
                "Joe Friel's general 7-zone heart rate system using actual lactate threshold "
                "heart rate. This provides more accurate zones based on individual physiology "
                "rather than estimated values."
            ),
            recommendations=[
                "Spend 80% of training time in zones 1-2 for aerobic base development",
                "Use zone 3 tempo training 1-2 times per week",
                "Zone 4 threshold training once per week maximum",
                "Zones 5-7 should be used sparingly with adequate recovery",
                "Adjust zones based on sport-specific demands when available"
            ]
        )


class JoeFrielRunningCalculator(LactateThresholdZoneCalculator):
    """
    Joe Friel for Running (7 zones) Heart Rate Calculator
    
    Running-specific heart rate zones from The Triathlete's Training Bible,
    optimized for running physiology and biomechanics.
    """
    
    def calculate_zones(
        self,
        max_heart_rate: Optional[int] = None,
        resting_heart_rate: Optional[int] = None,
        lthr: Optional[int] = None,
        age: Optional[int] = None
    ) -> HeartRateZoneResult:
        """Calculate Joe Friel running-specific 7-zone system"""
        # Priority: LTHR > max_heart_rate + age estimation
        if lthr is None:
            if max_heart_rate is None and age is None:
                raise InvalidParameterError("Either lthr, max_heart_rate, or age must be provided")

            if max_heart_rate is None:
                max_heart_rate = self.estimate_max_heart_rate(age)

            # Estimate LTHR from max HR - running LTHR tends to be slightly higher (87%)
            lthr = int(max_heart_rate * 0.87)
            logger.warning(f"Using estimated LTHR {lthr} from max HR {max_heart_rate}. For accurate zones, provide actual threshold HR.")

        # Estimate max HR from LTHR for reference (running LTHR is typically 87% of max HR)
        if max_heart_rate is None:
            estimated_max_hr = int(lthr / 0.87)
        else:
            estimated_max_hr = max_heart_rate
        
        zones = [
            self._create_lthr_zone(
                1, "Recovery", 0, 85, lthr,
                "Active recovery running for restoration",
                "Promote recovery between harder running sessions",
                ["Enhanced recovery", "Improved running economy", "Reduced muscle tension"],
                "30-60 minutes", "Very easy, should feel restorative"
            ),
            self._create_lthr_zone(
                2, "Aerobic", 85, 89, lthr,
                "Fundamental aerobic running base",
                "Build aerobic capacity and running efficiency",
                ["Improved running economy", "Enhanced fat oxidation", "Better biomechanics"],
                "45-120 minutes", "Easy, comfortable conversation pace"
            ),
            self._create_lthr_zone(
                3, "Tempo", 90, 94, lthr,
                "Steady aerobic running effort",
                "Improve lactate clearance and running rhythm",
                ["Enhanced lactate clearance", "Improved running efficiency", "Better pacing"],
                "20-60 minutes", "Moderately hard, comfortably hard"
            ),
            self._create_lthr_zone(
                4, "Lactate Threshold", 95, 99, lthr,
                "Running at lactate threshold pace",
                "Develop threshold pace and lactate tolerance",
                ["Increased threshold pace", "Enhanced lactate buffering", "Improved tempo runs"],
                "8-40 minutes", "Hard, focused effort at threshold"
            ),
            self._create_lthr_zone(
                5, "VO2max (5a)", 100, 102, lthr,
                "VO2max running intervals",
                "Develop maximum aerobic power for running",
                ["Increased VO2max", "Enhanced aerobic power", "Improved running speed"],
                "3-8 minutes in intervals", "Very hard, near maximum effort"
            ),
            self._create_lthr_zone(
                6, "Anaerobic (5b)", 103, 106, lthr,
                "Anaerobic running capacity training",
                "Develop speed and anaerobic power",
                ["Enhanced anaerobic capacity", "Improved speed endurance", "Better kick"],
                "30 seconds to 2 minutes", "Extremely hard, unsustainable"
            ),
            self._create_lthr_zone(
                7, "Neuromuscular (5c)", 107, 120, lthr,
                "Sprint and neuromuscular power development",
                "Develop maximum running speed and power",
                ["Enhanced running speed", "Improved neuromuscular coordination", "Sprint development"],
                "5-15 seconds", "All-out sprint speed"
            )
        ]
        
        return HeartRateZoneResult(
            method=HeartRateZoneMethod.JOE_FRIEL_RUNNING,
            method_name="Joe Friel for Running (7 zones)",
            max_heart_rate=estimated_max_hr,
            age=age,
            zones=zones,
            method_description=(
                "Joe Friel's running-specific 7-zone system using actual lactate threshold "
                "heart rate. This provides more accurate zones based on individual running "
                "physiology rather than estimated values."
            ),
            recommendations=[
                "Build base with 80% of weekly mileage in zones 1-2",
                "Include weekly tempo runs in zone 3",
                "Threshold runs (zone 4) once per week during build periods",
                "VO2max intervals (zone 5) 1-2 times per week maximum",
                "Use zones 6-7 for speed development and race preparation"
            ]
        )


class JoeFrielCyclingCalculator(LactateThresholdZoneCalculator):
    """
    Joe Friel for Cycling (7 zones) Heart Rate Calculator
    
    Cycling-specific heart rate zones from The Cyclist's Training Bible
    and The Triathlete's Training Bible.
    """
    
    def calculate_zones(
        self,
        max_heart_rate: Optional[int] = None,
        resting_heart_rate: Optional[int] = None,
        lthr: Optional[int] = None,
        age: Optional[int] = None
    ) -> HeartRateZoneResult:
        """Calculate Joe Friel cycling-specific 7-zone system"""
        # Priority: LTHR > max_heart_rate + age estimation
        if lthr is None:
            if max_heart_rate is None and age is None:
                raise InvalidParameterError("Either lthr, max_heart_rate, or age must be provided")

            if max_heart_rate is None:
                max_heart_rate = self.estimate_max_heart_rate(age)

            # Estimate LTHR from max HR - cycling LTHR tends to be lower (85%)
            lthr = int(max_heart_rate * 0.85)
            logger.warning(f"Using estimated LTHR {lthr} from max HR {max_heart_rate}. For accurate zones, provide actual threshold HR.")

        # Estimate max HR from LTHR for reference (cycling LTHR is typically 85% of max HR)
        if max_heart_rate is None:
            estimated_max_hr = int(lthr / 0.85)
        else:
            estimated_max_hr = max_heart_rate
        
        zones = [
            self._create_lthr_zone(
                1, "Recovery", 0, 81, lthr,
                "Active recovery cycling for restoration",
                "Promote recovery and maintain pedaling skills",
                ["Enhanced recovery", "Improved pedaling efficiency", "Reduced leg tension"],
                "30-90 minutes", "Very easy, spin to recover"
            ),
            self._create_lthr_zone(
                2, "Aerobic", 81, 89, lthr,
                "Fundamental aerobic cycling base",
                "Build aerobic capacity and cycling efficiency",
                ["Improved cycling economy", "Enhanced fat oxidation", "Better pedaling technique"],
                "60-180 minutes", "Easy, comfortable conversation"
            ),
            self._create_lthr_zone(
                3, "Tempo", 90, 93, lthr,
                "Steady aerobic cycling effort",
                "Improve lactate clearance and cycling efficiency",
                ["Enhanced lactate clearance", "Improved cycling economy", "Better pacing skills"],
                "20-90 minutes", "Moderately hard, sustainable"
            ),
            self._create_lthr_zone(
                4, "Lactate Threshold", 94, 99, lthr,
                "Cycling at functional threshold power",
                "Develop threshold power and lactate tolerance",
                ["Increased FTP", "Enhanced lactate buffering", "Improved time trial performance"],
                "8-40 minutes", "Hard, focused concentration required"
            ),
            self._create_lthr_zone(
                5, "VO2max (5a)", 100, 102, lthr,
                "VO2max cycling intervals",
                "Develop maximum aerobic power",
                ["Increased VO2max", "Enhanced aerobic power", "Improved climbing ability"],
                "3-8 minutes in intervals", "Very hard, near maximum"
            ),
            self._create_lthr_zone(
                6, "Anaerobic (5b)", 103, 106, lthr,
                "Anaerobic cycling capacity",
                "Develop anaerobic power and speed",
                ["Enhanced anaerobic capacity", "Improved sprint power", "Better attack capability"],
                "30 seconds to 3 minutes", "Extremely hard effort"
            ),
            self._create_lthr_zone(
                7, "Neuromuscular (5c)", 107, 120, lthr,
                "Sprint and neuromuscular power",
                "Develop maximum cycling power and speed",
                ["Enhanced sprint power", "Improved neuromuscular recruitment", "Maximum power output"],
                "5-15 seconds", "All-out sprint effort"
            )
        ]
        
        return HeartRateZoneResult(
            method=HeartRateZoneMethod.JOE_FRIEL_CYCLING,
            method_name="Joe Friel for Cycling (7 zones)",
            max_heart_rate=estimated_max_hr,
            age=age,
            zones=zones,
            method_description=(
                "Joe Friel's cycling-specific 7-zone system using actual lactate threshold "
                "heart rate. This provides more accurate zones based on individual cycling "
                "physiology rather than estimated values."
            ),
            recommendations=[
                "Build aerobic base with 70-80% of training in zones 1-2",
                "Include regular tempo work (zone 3) for endurance",
                "Threshold intervals (zone 4) 1-2 times per week",
                "VO2max work (zone 5) during build phases only",
                "Sprint training (zones 6-7) for power development"
            ]
        )


class AndyCogganCalculator(LactateThresholdZoneCalculator):
    """
    Andy Coggan (5 zones) Heart Rate Calculator
    
    Heart rate zones corresponding to the power zones described in
    "Training and Racing with a Power Meter" by Hunter Allen and Andy Coggan.
    """
    
    def calculate_zones(
        self,
        max_heart_rate: Optional[int] = None,
        resting_heart_rate: Optional[int] = None,
        lthr: Optional[int] = None,
        age: Optional[int] = None
    ) -> HeartRateZoneResult:
        """Calculate Andy Coggan 5-zone heart rate system"""
        # Priority: LTHR > max_heart_rate + age estimation
        if lthr is None:
            if max_heart_rate is None and age is None:
                raise InvalidParameterError("Either lthr, max_heart_rate, or age must be provided")

            if max_heart_rate is None:
                max_heart_rate = self.estimate_max_heart_rate(age)

            # Estimate LTHR from max HR (typically 86% for Coggan zones)
            lthr = int(max_heart_rate * 0.86)
            logger.warning(f"Using estimated LTHR {lthr} from max HR {max_heart_rate}. For accurate zones, provide actual threshold HR.")

        # Estimate max HR from LTHR for reference (LTHR is typically 86% of max HR for Coggan zones)
        if max_heart_rate is None:
            estimated_max_hr = int(lthr / 0.86)
        else:
            estimated_max_hr = max_heart_rate
        
        zones = [
            self._create_lthr_zone(
                1, "Active Recovery", 0, 68, lthr,
                "Very light activity for active recovery",
                "Promote recovery and maintain basic fitness",
                ["Enhanced recovery", "Improved circulation", "Basic aerobic maintenance"],
                "30-90 minutes", "Very easy, minimal effort"
            ),
            self._create_lthr_zone(
                2, "Endurance", 69, 83, lthr,
                "Basic aerobic endurance training",
                "Build aerobic base and improve fat utilization",
                ["Improved aerobic capacity", "Enhanced fat oxidation", "Increased capillary density"],
                "60-300 minutes", "Easy, comfortable conversation"
            ),
            self._create_lthr_zone(
                3, "Tempo", 84, 94, lthr,
                "Aerobic threshold and tempo training",
                "Improve aerobic capacity and lactate clearance",
                ["Enhanced lactate clearance", "Improved aerobic power", "Better endurance"],
                "20-90 minutes", "Moderately hard, some concentration needed"
            ),
            self._create_lthr_zone(
                4, "Lactate Threshold", 95, 105, lthr,
                "Lactate threshold and functional threshold training",
                "Develop threshold power and lactate tolerance",
                ["Increased threshold power", "Enhanced lactate buffering", "Improved race performance"],
                "8-40 minutes", "Hard, focused breathing pattern"
            ),
            self._create_lthr_zone(
                5, "VO2max", 106, 120, lthr,
                "VO2max and anaerobic capacity training",
                "Develop maximum aerobic and anaerobic power",
                ["Increased VO2max", "Enhanced anaerobic capacity", "Maximum power development"],
                "30 seconds to 8 minutes", "Very hard to maximal effort"
            )
        ]
        
        return HeartRateZoneResult(
            method=HeartRateZoneMethod.ANDY_COGGAN,
            method_name="Andy Coggan (5 zones)",
            max_heart_rate=estimated_max_hr,
            age=age,
            zones=zones,
            method_description=(
                "The Andy Coggan 5-zone heart rate system using actual lactate threshold "
                "heart rate, corresponding to the power zones from 'Training and Racing "
                "with a Power Meter'. This provides more accurate zones based on individual physiology."
            ),
            recommendations=[
                "Spend majority of training time in zones 1-2",
                "Zone 3 tempo work for aerobic development",
                "Zone 4 threshold training for performance gains",
                "Zone 5 intervals for maximum power development",
                "Use power data when available for more precise training"
            ]
        )


class USATRunningCalculator(LactateThresholdZoneCalculator):
    """
    USAT for Running (6 zones) Heart Rate Calculator
    
    Heart rate zones used by USA Triathlon coaches, specifically
    designed for running training in triathlon context.
    """
    
    def calculate_zones(
        self,
        max_heart_rate: Optional[int] = None,
        resting_heart_rate: Optional[int] = None,
        lthr: Optional[int] = None,
        age: Optional[int] = None
    ) -> HeartRateZoneResult:
        """Calculate USAT running-specific 6-zone system"""
        # Priority: LTHR > max_heart_rate + age estimation
        if lthr is None:
            if max_heart_rate is None and age is None:
                raise InvalidParameterError("Either lthr, max_heart_rate, or age must be provided")

            if max_heart_rate is None:
                max_heart_rate = self.estimate_max_heart_rate(age)

            # Estimate LTHR from max HR (87% for USAT running)
            lthr = int(max_heart_rate * 0.87)
            logger.warning(f"Using estimated LTHR {lthr} from max HR {max_heart_rate}. For accurate zones, provide actual threshold HR.")

        # Use provided max_heart_rate or estimate from LTHR
        if max_heart_rate is None:
            max_heart_rate = int(lthr / 0.87)
        
        zones = [
            self._create_lthr_zone(
                1, "Easy", 50, 65, lthr,
                "Very light aerobic training",
                "Active recovery and base aerobic development",
                ["Enhanced recovery", "Basic aerobic fitness", "Fat utilization"],
                "30-120 minutes", "Very comfortable, easy conversation"
            ),
            self._create_lthr_zone(
                2, "Moderate", 65, 80, lthr,
                "Moderate aerobic training intensity",
                "Build aerobic base and endurance",
                ["Improved aerobic capacity", "Enhanced endurance", "Better fat oxidation"],
                "45-180 minutes", "Comfortable, conversation possible"
            ),
            self._create_lthr_zone(
                3, "Threshold", 80, 90, lthr,
                "Aerobic threshold training",
                "Improve lactate clearance and aerobic power",
                ["Enhanced lactate clearance", "Improved aerobic threshold", "Better endurance"],
                "20-60 minutes", "Moderately hard, controlled breathing"
            ),
            self._create_lthr_zone(
                4, "Lactate Threshold", 90, 100, lthr,
                "Lactate threshold and tempo training",
                "Develop lactate threshold and race pace",
                ["Increased lactate threshold", "Enhanced race preparation", "Improved pace tolerance"],
                "10-40 minutes", "Hard, focused effort required"
            ),
            self._create_lthr_zone(
                5, "VO2max", 100, 110, lthr,
                "VO2max and high aerobic power",
                "Develop maximum aerobic power",
                ["Increased VO2max", "Enhanced aerobic power", "Improved speed"],
                "2-8 minutes in intervals", "Very hard, near maximum"
            ),
            self._create_lthr_zone(
                6, "Anaerobic", 110, 120, lthr,
                "Anaerobic power and speed development",
                "Develop anaerobic capacity and speed",
                ["Enhanced anaerobic capacity", "Improved speed", "Better sprint capability"],
                "15 seconds to 2 minutes", "Maximal effort"
            )
        ]
        
        return HeartRateZoneResult(
            method=HeartRateZoneMethod.USAT_RUNNING,
            method_name="USAT for Running (6 zones)",
            max_heart_rate=max_heart_rate,
            age=age,
            zones=zones,
            method_description=(
                "The USAT running zones are specifically designed for triathlon training "
                "by USA Triathlon coaches. This 6-zone system provides comprehensive "
                "guidance for running training within the triathlon context."
            ),
            recommendations=[
                "Build base with 70-80% of training in zones 1-2",
                "Use zone 3 for aerobic threshold development",
                "Zone 4 threshold work 1-2 times per week",
                "Zone 5 intervals for VO2max development",
                "Zone 6 for speed and anaerobic power"
            ]
        )


class EightyTwentyRunningCalculator(LactateThresholdZoneCalculator):
    """
    80/20 Running (7 zones) Heart Rate Calculator
    
    Matt Fitzgerald's polarized training system with 7 zones,
    emphasizing 80% low intensity and 20% high intensity training.
    """
    
    def calculate_zones(
        self,
        max_heart_rate: Optional[int] = None,
        resting_heart_rate: Optional[int] = None,
        lthr: Optional[int] = None,
        age: Optional[int] = None
    ) -> HeartRateZoneResult:
        """Calculate 80/20 Running 7-zone system"""
        # Priority: LTHR > max_heart_rate + age estimation
        if lthr is None:
            if max_heart_rate is None and age is None:
                raise InvalidParameterError("Either lthr, max_heart_rate, or age must be provided")

            if max_heart_rate is None:
                max_heart_rate = self.estimate_max_heart_rate(age)

            # Estimate LTHR from max HR (87% for 80/20 running)
            lthr = int(max_heart_rate * 0.87)
            logger.warning(f"Using estimated LTHR {lthr} from max HR {max_heart_rate}. For accurate zones, provide actual threshold HR.")

        # Use provided max_heart_rate or estimate from LTHR
        if max_heart_rate is None:
            max_heart_rate = int(lthr / 0.87)
        
        zones = [
            self._create_lthr_zone(
                1, "Recovery", 0, 81, lthr,
                "Active recovery and very easy aerobic activity",
                "Promote recovery and maintain aerobic function",
                ["Enhanced recovery", "Active restoration", "Improved circulation"],
                "30-90 minutes", "Very easy, restorative feel"
            ),
            self._create_lthr_zone(
                2, "Aerobic Base", 81, 89, lthr,
                "Fundamental aerobic base development",
                "Build aerobic capacity and fat burning efficiency",
                ["Improved aerobic capacity", "Enhanced fat oxidation", "Better endurance"],
                "45-180 minutes", "Easy, comfortable conversation pace"
            ),
            self._create_lthr_zone(
                3, "Moderate Aerobic", 90, 94, lthr,
                "Moderate aerobic training - generally avoided in 80/20",
                "Limited use in polarized training model",
                ["Moderate aerobic development", "Lactate clearance improvement"],
                "Limited use", "Moderate - generally avoided in 80/20"
            ),
            self._create_lthr_zone(
                4, "Threshold", 95, 99, lthr,
                "Lactate threshold and tempo training",
                "Develop threshold power and lactate tolerance",
                ["Increased lactate threshold", "Enhanced threshold power", "Race preparation"],
                "8-40 minutes", "Hard, sustainable effort"
            ),
            self._create_lthr_zone(
                5, "VO2max", 100, 102, lthr,
                "VO2max intervals and aerobic power",
                "Develop maximum aerobic power",
                ["Increased VO2max", "Enhanced aerobic power", "Improved running speed"],
                "3-8 minutes in intervals", "Very hard, near maximum"
            ),
            self._create_lthr_zone(
                6, "Anaerobic", 103, 106, lthr,
                "Anaerobic capacity and speed endurance",
                "Develop anaerobic power and speed",
                ["Enhanced anaerobic capacity", "Improved speed endurance", "Better finishing kick"],
                "30 seconds to 2 minutes", "Extremely hard, unsustainable"
            ),
            self._create_lthr_zone(
                7, "Sprint", 107, 120, lthr,
                "Maximum sprint power and neuromuscular development",
                "Develop maximum speed and power",
                ["Enhanced sprint speed", "Improved neuromuscular power", "Maximum running speed"],
                "5-15 seconds", "All-out sprint effort"
            )
        ]
        
        return HeartRateZoneResult(
            method=HeartRateZoneMethod.EIGHTY_TWENTY_RUNNING,
            method_name="80/20 Running (7 zones)",
            max_heart_rate=max_heart_rate,
            age=age,
            zones=zones,
            method_description=(
                "The 80/20 Running method is based on Matt Fitzgerald's polarized "
                "training approach. It emphasizes 80% low-intensity training (zones 1-2) "
                "and 20% high-intensity training (zones 4-7), while minimizing "
                "moderate intensity work (zone 3)."
            ),
            recommendations=[
                "80% of weekly training should be in zones 1-2 (low intensity)",
                "20% of weekly training should be in zones 4-7 (high intensity)",
                "Minimize time in zone 3 (moderate intensity)",
                "Focus on polarized distribution for optimal adaptation",
                "Use zones 5-7 for speed and power development"
            ]
        )


class HeartRateZoneAnalyzer(FitnessAnalyzer):
    """
    Comprehensive Heart Rate Zone Analyzer
    
    Provides analysis and calculation of heart rate zones using multiple
    methodologies with detailed explanations and training recommendations.
    """
    
    def __init__(self):
        self.calculators = {
            # Maximum HR based methods
            HeartRateZoneMethod.BCF_ABCC_WCPP_REVISED: BCFABCCWCPPRevisedCalculator(),
            HeartRateZoneMethod.PETER_KEEN: PeterKeenCalculator(),
            HeartRateZoneMethod.RIC_STERN: RicSternCalculator(),
            HeartRateZoneMethod.SALLY_EDWARDS: SallyEdwardsCalculator(),
            HeartRateZoneMethod.TIMEX: TimexCalculator(),
            HeartRateZoneMethod.MYPROCOACH: MyProCoachCalculator(),
            
            # Lactate threshold based methods
            HeartRateZoneMethod.JOE_FRIEL: JoeFrielCalculator(),
            HeartRateZoneMethod.JOE_FRIEL_RUNNING: JoeFrielRunningCalculator(),
            HeartRateZoneMethod.JOE_FRIEL_CYCLING: JoeFrielCyclingCalculator(),
            HeartRateZoneMethod.ANDY_COGGAN: AndyCogganCalculator(),
            HeartRateZoneMethod.USAT_RUNNING: USATRunningCalculator(),
            HeartRateZoneMethod.EIGHTY_TWENTY_RUNNING: EightyTwentyRunningCalculator()
        }
    
    def analyze(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """
        Analyze heart rate zones based on filter criteria

        Args:
            filter_criteria: Analytics filter criteria containing user preferences

        Returns:
            AnalyticsResult containing heart rate zone analysis
        """
        # This method would typically integrate with user data from filter_criteria
        # For now, we'll return a placeholder result
        _ = filter_criteria  # Acknowledge parameter for future use
        data = {
            "message": "Use calculate_heart_rate_zones method for zone calculations",
            "available_methods": [method.value for method in HeartRateZoneMethod]
        }
        
        return AnalyticsResult(
            analytics_type=AnalyticsType.HEART_RATE_ANALYSIS,
            data=data,
            metadata={
                "analyzer": "HeartRateZoneAnalyzer",
                "methods_available": len(self.calculators)
            }
        )
    
    def calculate_heart_rate_zones(
        self,
        max_heart_rate: Optional[int] = None,
        resting_heart_rate: Optional[int] = None,
        lthr: Optional[int] = None,
        age: Optional[int] = None,
        method: Union[HeartRateZoneMethod, str] = HeartRateZoneMethod.BCF_ABCC_WCPP_REVISED
    ) -> HeartRateZoneResult:
        """
        Calculate heart rate zones using specified method

        Args:
            max_heart_rate: Known maximum heart rate in BPM
            resting_heart_rate: Known resting heart rate in BPM
            lthr: Known lactate threshold heart rate in BPM
            age: Age in years (used to estimate max HR if not provided)
            method: Heart rate zone calculation method

        Returns:
            HeartRateZoneResult containing calculated zones and guidance

        Raises:
            InvalidParameterError: If no sufficient parameters provided
            AnalyticsError: If calculation fails
        """
        try:
            # Convert string method to enum if needed
            if isinstance(method, str):
                try:
                    method = HeartRateZoneMethod(method)
                except ValueError:
                    available = [m.value for m in HeartRateZoneMethod]
                    raise InvalidParameterError(
                        f"Invalid method '{method}'. Available: {available}"
                    )

            # Validate heart rate ranges if provided
            if max_heart_rate is not None and (max_heart_rate < 100 or max_heart_rate > 250):
                raise InvalidParameterError(
                    f"Maximum heart rate {max_heart_rate} is outside reasonable range (100-250 BPM)"
                )

            if resting_heart_rate is not None and (resting_heart_rate < 30 or resting_heart_rate > 100):
                raise InvalidParameterError(
                    f"Resting heart rate {resting_heart_rate} is outside reasonable range (30-100 BPM)"
                )

            if lthr is not None and (lthr < 80 or lthr > 220):
                raise InvalidParameterError(
                    f"Lactate threshold heart rate {lthr} is outside reasonable range (80-220 BPM)"
                )

            if max_heart_rate is not None and lthr is not None and lthr >= max_heart_rate:
                raise InvalidParameterError(
                    f"Lactate threshold heart rate ({lthr}) must be less than max heart rate ({max_heart_rate})"
                )

            # Get calculator and compute zones
            calculator = self.calculators[method]
            result = calculator.calculate_zones(
                max_heart_rate=max_heart_rate,
                resting_heart_rate=resting_heart_rate,
                lthr=lthr,
                age=age
            )

            return result
            
        except Exception as e:
            logger.error(f"Error calculating heart rate zones: {str(e)}")
            raise AnalyticsError(f"Heart rate zone calculation failed: {str(e)}")
    
    def compare_methods(
        self,
        max_heart_rate: Optional[int] = None,
        resting_heart_rate: Optional[int] = None,
        lthr: Optional[int] = None,
        age: Optional[int] = None,
        methods: Optional[List[Union[HeartRateZoneMethod, str]]] = None
    ) -> Dict[str, HeartRateZoneResult]:
        """
        Compare multiple heart rate zone calculation methods

        Args:
            max_heart_rate: Known maximum heart rate in BPM
            resting_heart_rate: Known resting heart rate in BPM
            lthr: Known lactate threshold heart rate in BPM
            age: Age in years (used to estimate max HR if not provided)
            methods: List of methods to compare (defaults to all methods)

        Returns:
            Dictionary mapping method names to HeartRateZoneResult objects
        """
        if methods is None:
            methods = list(HeartRateZoneMethod)
        
        results = {}
        for method in methods:
            try:
                result = self.calculate_heart_rate_zones(
                    max_heart_rate=max_heart_rate,
                    resting_heart_rate=resting_heart_rate,
                    lthr=lthr,
                    age=age,
                    method=method
                )
                results[result.method_name] = result
            except Exception as e:
                logger.warning(f"Failed to calculate zones for {method}: {str(e)}")

        return results
    
    def get_zone_recommendations(
        self,
        method: Union[HeartRateZoneMethod, str] = HeartRateZoneMethod.BCF_ABCC_WCPP_REVISED,
        training_goal: str = "general_fitness"
    ) -> List[str]:
        """
        Get training recommendations based on method and goals
        
        Args:
            method: Heart rate zone calculation method
            training_goal: Training objective ("general_fitness", "weight_loss", 
                          "endurance", "performance", "recovery")
            
        Returns:
            List of training recommendations
        """
        if isinstance(method, str):
            method = HeartRateZoneMethod(method)
        
        base_recommendations = {
            HeartRateZoneMethod.BCF_ABCC_WCPP_REVISED: [
                "Focus 70-80% of training in zones 1-3",
                "Use zone 4 for tempo work 1-2x per week",
                "Limit zone 5-7 training to 1-2 sessions per week"
            ],
            HeartRateZoneMethod.PETER_KEEN: [
                "Make Level 2 the foundation - minimum 3 sessions per week",
                "Use Level 1 for recovery and active rest",
                "Add Level 3 twice per week for threshold development"
            ],
            HeartRateZoneMethod.RIC_STERN: [
                "Build aerobic base with zones 2-3",
                "Use zone 4 as preparation for threshold work",
                "Limit zones 6-7 to specific training phases"
            ],
            HeartRateZoneMethod.JOE_FRIEL: [
                "Follow 80/20 principle - 80% zones 1-2, 20% zones 3-7",
                "Zone 3 tempo work 1-2 times per week",
                "Threshold training (zone 4) once per week maximum"
            ],
            HeartRateZoneMethod.JOE_FRIEL_RUNNING: [
                "Build base with 80% weekly mileage in zones 1-2",
                "Weekly tempo runs in zone 3",
                "Threshold runs (zone 4) during build periods"
            ],
            HeartRateZoneMethod.JOE_FRIEL_CYCLING: [
                "70-80% of training in zones 1-2 for aerobic base",
                "Regular tempo work (zone 3) for endurance",
                "Threshold intervals (zone 4) 1-2 times per week"
            ],
            HeartRateZoneMethod.ANDY_COGGAN: [
                "Majority of training time in zones 1-2",
                "Zone 3 tempo work for aerobic development",
                "Zone 4 threshold training for performance gains"
            ],
            HeartRateZoneMethod.USAT_RUNNING: [
                "Build base with 70-80% of training in zones 1-2",
                "Zone 3 for aerobic threshold development",
                "Zone 4 threshold work 1-2 times per week"
            ],
            HeartRateZoneMethod.EIGHTY_TWENTY_RUNNING: [
                "80% easy (zones 1-2), 20% hard (zones 4-7)",
                "Avoid zone 3 - neither easy nor hard enough",
                "Monitor training distribution weekly"
            ]
        }
        
        goal_specific = {
            "weight_loss": [
                "Prioritize fat-burning zones (Zone 2 equivalent)",
                "Include longer, moderate-intensity sessions",
                "Maintain consistency over intensity"
            ],
            "endurance": [
                "Focus on aerobic base development",
                "Include regular tempo training",
                "Gradually increase training volume"
            ],
            "performance": [
                "Include threshold and VO2max training",
                "Periodize high-intensity work",
                "Monitor recovery carefully"
            ]
        }
        
        recommendations = base_recommendations.get(method, [
            "Follow the 80/20 rule - 80% easy, 20% hard",
            "Include recovery sessions regularly",
            "Progress intensity gradually"
        ])
        
        if training_goal in goal_specific:
            recommendations.extend(goal_specific[training_goal])
        
        return recommendations

    # ========== Calculator Interface Methods ==========
    
    def get_available_methods(self) -> List[HeartRateZoneMethod]:
        """
        Get all available heart rate zone calculation methods
        
        Returns:
            List of available HeartRateZoneMethod enums
        """
        return list(self.calculators.keys())
    
    def get_method_info(self, method: Union[HeartRateZoneMethod, str]) -> Dict[str, Any]:
        """
        Get detailed information about a specific heart rate zone method
        
        Args:
            method: Heart rate zone calculation method
            
        Returns:
            Dictionary containing method information
            
        Raises:
            InvalidParameterError: If method is not available
        """
        if isinstance(method, str):
            try:
                method = HeartRateZoneMethod(method)
            except ValueError:
                available = [m.value for m in HeartRateZoneMethod]
                raise InvalidParameterError(
                    f"Invalid method '{method}'. Available: {available}"
                )
        
        if method not in self.calculators:
            raise InvalidParameterError(f"Method {method.value} not available")
        
        calculator = self.calculators[method]
        
        # Get method info by creating a sample calculation
        try:
            sample_result = calculator.calculate_zones(max_heart_rate=180, age=30)
            
            info = {
                "method": method.value,
                "method_name": sample_result.method_name,
                "method_description": sample_result.method_description,
                "zone_count": len(sample_result.zones),
                "calculator_type": type(calculator).__name__,
                "is_lactate_threshold_based": isinstance(calculator, LactateThresholdZoneCalculator),
                "recommendations": sample_result.recommendations,
                "zone_names": [zone.zone_name for zone in sample_result.zones]
            }
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get method info for {method.value}: {str(e)}")
            raise AnalyticsError(f"Cannot retrieve method information: {str(e)}")
    
    def get_calculator(self, method: Union[HeartRateZoneMethod, str]) -> HeartRateZoneCalculator:
        """
        Get the calculator instance for a specific method
        
        Args:
            method: Heart rate zone calculation method
            
        Returns:
            HeartRateZoneCalculator instance
            
        Raises:
            InvalidParameterError: If method is not available
        """
        if isinstance(method, str):
            try:
                method = HeartRateZoneMethod(method)
            except ValueError:
                available = [m.value for m in HeartRateZoneMethod]
                raise InvalidParameterError(
                    f"Invalid method '{method}'. Available: {available}"
                )
        
        if method not in self.calculators:
            raise InvalidParameterError(f"Method {method.value} not available")
        
        return self.calculators[method]
    
    def get_methods_by_type(self, method_type: str = "all") -> Dict[str, List[HeartRateZoneMethod]]:
        """
        Get methods grouped by type (max_hr_based, lactate_threshold_based, or all)
        
        Args:
            method_type: Type filter ("max_hr_based", "lactate_threshold_based", "all")
            
        Returns:
            Dictionary with method types as keys and lists of methods as values
        """
        max_hr_methods = []
        lactate_threshold_methods = []
        
        for method, calculator in self.calculators.items():
            if isinstance(calculator, LactateThresholdZoneCalculator):
                lactate_threshold_methods.append(method)
            else:
                max_hr_methods.append(method)
        
        result = {}
        
        if method_type in ["all", "max_hr_based"]:
            result["max_hr_based"] = max_hr_methods
        
        if method_type in ["all", "lactate_threshold_based"]:
            result["lactate_threshold_based"] = lactate_threshold_methods
        
        return result
    
    def get_method_categories(self) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed categorization of all available methods
        
        Returns:
            Dictionary with method categories and their details
        """
        max_hr_methods = []
        lactate_threshold_methods = []
        
        for method, calculator in self.calculators.items():
            method_info = {
                "method": method,
                "name": method.value.replace('_', ' ').title(),
                "calculator_class": type(calculator).__name__,
                "zone_count": self._get_zone_count(calculator)
            }
            
            if isinstance(calculator, LactateThresholdZoneCalculator):
                lactate_threshold_methods.append(method_info)
            else:
                max_hr_methods.append(method_info)
        
        return {
            "max_hr_based": {
                "description": "Methods based on maximum heart rate percentages",
                "reference_point": "Maximum Heart Rate (HRmax)",
                "methods": max_hr_methods
            },
            "lactate_threshold_based": {
                "description": "Methods based on lactate threshold heart rate",
                "reference_point": "Lactate Threshold Heart Rate (LTHR)",
                "methods": lactate_threshold_methods
            }
        }
    
    def _get_zone_count(self, calculator: HeartRateZoneCalculator) -> int:
        """Helper method to get zone count for a calculator"""
        try:
            result = calculator.calculate_zones(max_heart_rate=180, age=30)
            return len(result.zones)
        except Exception:
            return 0
    
    def validate_method_compatibility(self, method: Union[HeartRateZoneMethod, str], 
                                    sport: str = "general") -> Dict[str, Any]:
        """
        Validate if a method is compatible with a specific sport
        
        Args:
            method: Heart rate zone calculation method
            sport: Sport type ("running", "cycling", "triathlon", "general")
            
        Returns:
            Dictionary with compatibility information
        """
        if isinstance(method, str):
            try:
                method = HeartRateZoneMethod(method)
            except ValueError:
                available = [m.value for m in HeartRateZoneMethod]
                raise InvalidParameterError(
                    f"Invalid method '{method}'. Available: {available}"
                )
        
        # Sport-specific compatibility matrix
        compatibility = {
            "running": {
                HeartRateZoneMethod.JOE_FRIEL_RUNNING: {"compatible": True, "optimal": True},
                HeartRateZoneMethod.USAT_RUNNING: {"compatible": True, "optimal": True},
                HeartRateZoneMethod.EIGHTY_TWENTY_RUNNING: {"compatible": True, "optimal": True},
                HeartRateZoneMethod.JOE_FRIEL_CYCLING: {"compatible": False, "optimal": False},
            },
            "cycling": {
                HeartRateZoneMethod.JOE_FRIEL_CYCLING: {"compatible": True, "optimal": True},
                HeartRateZoneMethod.ANDY_COGGAN: {"compatible": True, "optimal": True},
                HeartRateZoneMethod.BCF_ABCC_WCPP_REVISED: {"compatible": True, "optimal": True},
                HeartRateZoneMethod.PETER_KEEN: {"compatible": True, "optimal": True},
                HeartRateZoneMethod.JOE_FRIEL_RUNNING: {"compatible": False, "optimal": False},
            },
            "triathlon": {
                HeartRateZoneMethod.USAT_RUNNING: {"compatible": True, "optimal": True},
                HeartRateZoneMethod.JOE_FRIEL: {"compatible": True, "optimal": True},
                HeartRateZoneMethod.JOE_FRIEL_RUNNING: {"compatible": True, "optimal": False},
                HeartRateZoneMethod.JOE_FRIEL_CYCLING: {"compatible": True, "optimal": False},
            }
        }
        
        # Default compatibility for methods not specifically listed
        default_compatibility = {"compatible": True, "optimal": sport == "general"}
        
        sport_compat = compatibility.get(sport, {})
        method_compat = sport_compat.get(method, default_compatibility)
        
        return {
            "method": method.value,
            "sport": sport,
            "compatible": method_compat["compatible"],
            "optimal": method_compat["optimal"],
            "reason": self._get_compatibility_reason(method, sport, method_compat)
        }
    
    def _get_compatibility_reason(self, method: HeartRateZoneMethod, sport: str, 
                                 compatibility: Dict[str, bool]) -> str:
        """Helper method to provide compatibility reasoning"""
        if not compatibility["compatible"]:
            if sport == "running" and "cycling" in method.value:
                return "This method is specifically designed for cycling"
            elif sport == "cycling" and "running" in method.value:
                return "This method is specifically designed for running"
            else:
                return "Method not recommended for this sport"
        
        if compatibility["optimal"]:
            if sport in method.value:
                return "Method specifically optimized for this sport"
            else:
                return "Well-suited method for this sport"
        else:
            return "Compatible but not specifically optimized for this sport"

    def calculate_zones(
        self,
        method: HeartRateZoneMethod,
        max_heart_rate: Optional[int] = None,
        resting_heart_rate: Optional[int] = None,
        lthr: Optional[int] = None,
        age: Optional[int] = None
    ) -> List:
        """
        Calculate heart rate zones using specified method (wrapper for analytics route compatibility)

        Args:
            method: Heart rate zone calculation method
            max_heart_rate: Maximum heart rate in BPM
            resting_heart_rate: Resting heart rate in BPM
            lthr: Lactate threshold heart rate in BPM
            age: Age in years

        Returns:
            List of heart rate zone objects
        """
        result = self.calculate_heart_rate_zones(
            max_heart_rate=max_heart_rate,
            resting_heart_rate=resting_heart_rate,
            lthr=lthr,
            age=age,
            method=method
        )
        return result.zones



# Example usage and testing
if __name__ == "__main__":
    # Demo the heart rate zone calculator
    analyzer = HeartRateZoneAnalyzer()
    
    # Example: Calculate zones for a 35-year-old athlete
    result = analyzer.calculate_heart_rate_zones(age=35, max_heart_rate=190, method=HeartRateZoneMethod.MYPROCOACH)
    
    print(f"Heart Rate Zones - {result.method_name}")
    print("=" * 50)
    print(f"Max Heart Rate: {result.max_heart_rate} BPM")
    print()
    
    for zone in result.zones:
        hr_min, hr_max = zone.heart_rate_range
        pct_min, pct_max = zone.percentage_range
        print(f"Zone {zone.zone_number}: {zone.zone_name}")
        print(f"  {hr_min}-{hr_max} BPM ({pct_min:.0f}-{pct_max:.0f}%)")
        print(f"  {zone.purpose}")
        print()

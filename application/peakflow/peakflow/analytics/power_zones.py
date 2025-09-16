#!/usr/bin/env python3
"""
Power Zones Analytics Module

This module provides comprehensive power zone calculations based on various
methodologies for running training including:
- Steve Palladino Power Zones (7 zones) - Running FTP/CP based zones
- Stryd Running Power Zones (5 zones) - Stryd-specific running power zones  
- Critical Power Zones (7 zones) - Based on Critical Power model

Each method provides power ranges with detailed explanations of training purposes
and physiological adaptations for optimal running training prescription.

References:
- Steve Palladino: https://docs.google.com/document/d/e/2PACX-1vSS2mB3I3M_193Al8Kx02fSuDrK9uS8zJLqKv5WSQPcCEgPh19RPxMMbzk7OxKg3-A2QZkQ6_vDLR0q/pub
- Stryd Power Zones: https://support.stryd.com/hc/en-us/articles/360039774153-Power-Zones
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


class PowerZoneMethod(Enum):
    """Available power zone calculation methods"""
    STEVE_PALLADINO = "steve_palladino"  # 7 zones - Running FTP/CP based
    STRYD_RUNNING = "stryd_running"  # 7 zones - Stryd running power zones
    CRITICAL_POWER = "critical_power"  # 7 zones - Critical Power model


@dataclass
class PowerZone:
    """Represents a single power training zone"""
    zone_number: int
    zone_name: str
    power_range: Tuple[float, float]  # (min_power, max_power) in watts
    percentage_range: Tuple[float, float]  # Percentage of FTP/CP
    description: str = ""
    purpose: str = ""
    physiological_adaptations: str = ""
    duration_guidance: str = ""
    effort_level: str = ""


@dataclass 
class PowerZoneResult:
    """Power zone calculation results"""
    method: PowerZoneMethod
    zones: List[PowerZone]
    threshold_power: float  # FTP or CP in watts
    normalized_power: float  # Power normalized to body weight (W/kg)
    analytics_type: AnalyticsType
    timestamp: datetime
    calculation_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.zones:
            raise InvalidParameterError("Power zone result must contain at least one zone")


class PowerZoneCalculator(ABC):
    """Abstract base class for power zone calculations"""
    
    @abstractmethod
    def calculate_zones(self, threshold_power: float, body_weight: Optional[float] = None) -> List[PowerZone]:
        """
        Calculate power zones based on threshold power
        
        Args:
            threshold_power: FTP or Critical Power in watts
            body_weight: Body weight in kg (optional, for normalization)
            
        Returns:
            List of PowerZone objects
        """
        pass
    
    @abstractmethod
    def get_method_name(self) -> PowerZoneMethod:
        """Return the calculation method identifier"""
        pass
    
    @abstractmethod
    def get_method_description(self) -> str:
        """Return description of the calculation method"""
        pass


class StevePalladinoCalculator(PowerZoneCalculator):
    """
    Steve Palladino Power Zone Calculator for Running
    
    Based on Steve Palladino's power zone methodology:
    Zone 1: Easy Running (50-80% FTP)
      - 1A: Post Interval Recovery (50-65%)
      - 1B: Easy Warm-Up (65-75%) 
      - 1C: Easy Aerobic Running (75-80%)
    Zone 2: Endurance / Long Run (81-87% FTP)
    Zone 3: Threshold Stimulus (88-101% FTP)
      - 3A: Extensive Threshold (88-94%)
      - 3B: Intensive Threshold (95-101%)
    Zone 4: Supra Threshold (102-105% FTP)
    Zone 5: Maximal Aerobic Power (106-116% FTP)
    Zone 6: Anaerobic Power (117-150% FTP)
    Zone 7: Sprint / Maximal Power (>150% FTP)
    """
    
    def calculate_zones(self, threshold_power: float, body_weight: Optional[float] = None) -> List[PowerZone]:
        """Calculate Steve Palladino running power zones"""
        if threshold_power <= 0:
            raise InvalidParameterError("Threshold power must be positive")
        
        zones = [
            PowerZone(
                zone_number=1,
                zone_name="Easy Running",
                power_range=(threshold_power * 0.50, threshold_power * 0.80),
                percentage_range=(50, 80),
                description="Easy aerobic running including recovery, warm-up, and easy aerobic runs",
                purpose="Aerobic base development, recovery, preparation",
                physiological_adaptations="Improved fat oxidation, mitochondrial density, capillarization",
                duration_guidance="Can be sustained for hours",
                effort_level="Very easy to comfortable"
            ),
            PowerZone(
                zone_number=2,
                zone_name="Endurance / Long Run", 
                power_range=(threshold_power * 0.81, threshold_power * 0.87),
                percentage_range=(81, 87),
                description="Typical power for long runs and overdistance training",
                purpose="Aerobic endurance development, metabolic efficiency",
                physiological_adaptations="Enhanced aerobic capacity, improved fat utilization",
                duration_guidance="1-4+ hours depending on fitness",
                effort_level="Moderate, conversational"
            ),
            PowerZone(
                zone_number=3,
                zone_name="Threshold Stimulus",
                power_range=(threshold_power * 0.88, threshold_power * 1.01),
                percentage_range=(88, 101),
                description="Tempo runs and threshold work - sweet spot to intensive threshold",
                purpose="Lactate threshold development, metabolic flexibility",
                physiological_adaptations="Improved lactate clearance, buffering capacity",
                duration_guidance="15-60 minutes continuous or intervals",
                effort_level="Comfortably hard to moderately hard"
            ),
            PowerZone(
                zone_number=4,
                zone_name="Supra Threshold",
                power_range=(threshold_power * 1.02, threshold_power * 1.05),
                percentage_range=(102, 105),
                description="Above threshold work, typically intervals",
                purpose="Lactate tolerance, anaerobic capacity development",
                physiological_adaptations="Improved anaerobic power, lactate buffering",
                duration_guidance="5-15 minute intervals with recovery",
                effort_level="Hard"
            ),
            PowerZone(
                zone_number=5,
                zone_name="Maximal Aerobic Power",
                power_range=(threshold_power * 1.06, threshold_power * 1.16),
                percentage_range=(106, 116),
                description="Max aerobic work, VO2max intervals",
                purpose="VO2max development, aerobic power",
                physiological_adaptations="Increased VO2max, cardiac output, oxygen uptake",
                duration_guidance="3-8 minute intervals with equal recovery",
                effort_level="Very hard, near maximum sustainable"
            ),
            PowerZone(
                zone_number=6,
                zone_name="Anaerobic Power",
                power_range=(threshold_power * 1.17, threshold_power * 1.50),
                percentage_range=(117, 150),
                description="Anaerobic work, short intervals or time trials",
                purpose="Anaerobic capacity, neuromuscular power",
                physiological_adaptations="Improved anaerobic enzyme activity, phosphocreatine system",
                duration_guidance="30 seconds to 3 minutes with long recovery",
                effort_level="Extremely hard, unsustainable"
            ),
            PowerZone(
                zone_number=7,
                zone_name="Sprint / Maximal Power",
                power_range=(threshold_power * 1.51, threshold_power * 3.00),
                percentage_range=(151, 300),
                description="Maximal power sprints",
                purpose="Neuromuscular power, sprint speed",
                physiological_adaptations="Improved neuromuscular coordination, peak power output",
                duration_guidance="5-20 seconds with full recovery",
                effort_level="All-out maximum effort"
            )
        ]
        
        logger.info(f"Calculated Steve Palladino zones for FTP: {threshold_power}W")
        return zones
    
    def get_method_name(self) -> PowerZoneMethod:
        return PowerZoneMethod.STEVE_PALLADINO
        
    def get_method_description(self) -> str:
        return "Steve Palladino 7-zone running power system based on Functional Threshold Power"


class StrydRunningCalculator(PowerZoneCalculator):
    """
    Stryd Running Power Zone Calculator
    
    Based on official Stryd Powercenter zones for running:
    - Zone 1: Easy (65-80% of critical power)
    - Zone 2: Moderate (80-90% of critical power) 
    - Zone 3: Threshold (90-100% of critical power)
    - Zone 4: Interval (100-115% of critical power)
    - Zone 5: Repetition (115-130% of critical power)
    
    Reference: Stryd Powercenter official zones from Steve Palladino's document
    """
    
    def calculate_zones(self, threshold_power: float, body_weight: Optional[float] = None) -> List[PowerZone]:
        """Calculate Stryd running power zones (5 zones)"""
        if threshold_power <= 0:
            raise InvalidParameterError("Threshold power must be positive")
            
        zones = [
            PowerZone(
                zone_number=1,
                zone_name="Easy",
                power_range=(threshold_power * 0.65, threshold_power * 0.80),
                percentage_range=(65, 80),
                description="Easy aerobic running, recovery and base building",
                purpose="Aerobic base development, recovery, fat oxidation",
                physiological_adaptations="Mitochondrial development, improved fat metabolism, enhanced recovery",
                duration_guidance="45 minutes to several hours",
                effort_level="Easy, conversational pace"
            ),
            PowerZone(
                zone_number=2,
                zone_name="Moderate",
                power_range=(threshold_power * 0.80, threshold_power * 0.90),
                percentage_range=(80, 90),
                description="Moderate aerobic running, endurance development",
                purpose="Aerobic capacity development, endurance, long run pace",
                physiological_adaptations="Increased capillarization, cardiac output, aerobic efficiency",
                duration_guidance="30 minutes to 3+ hours",
                effort_level="Moderate, controlled effort"
            ),
            PowerZone(
                zone_number=3,
                zone_name="Threshold",
                power_range=(threshold_power * 0.90, threshold_power * 1.00),
                percentage_range=(90, 100),
                description="Lactate threshold training, tempo runs",
                purpose="Lactate threshold development, metabolic efficiency, tempo training",
                physiological_adaptations="Improved lactate clearance and buffering, threshold power",
                duration_guidance="20-60 minutes continuous or long intervals",
                effort_level="Comfortably hard, controlled breathing"
            ),
            PowerZone(
                zone_number=4,
                zone_name="Interval",
                power_range=(threshold_power * 1.00, threshold_power * 1.15),
                percentage_range=(100, 115),
                description="Above threshold interval training, VO2max development",
                purpose="VO2max improvement, aerobic power, race pace training",
                physiological_adaptations="Increased VO2max, improved oxygen utilization, lactate tolerance",
                duration_guidance="3-15 minutes with recovery intervals",
                effort_level="Hard to very hard, focused effort"
            ),
            PowerZone(
                zone_number=5,
                zone_name="Repetition",
                power_range=(threshold_power * 1.15, threshold_power * 1.30),
                percentage_range=(115, 130),
                description="High-intensity repetitions, neuromuscular power",
                purpose="Neuromuscular power, anaerobic capacity, speed development",
                physiological_adaptations="Improved neuromuscular coordination, anaerobic power, speed",
                duration_guidance="30 seconds to 5 minutes with full recovery",
                effort_level="Very hard to maximum effort"
            )
        ]
        
        logger.info(f"Calculated Stryd running zones (5 zones) for Critical Power: {threshold_power}W")
        return zones
    
    def get_method_name(self) -> PowerZoneMethod:
        return PowerZoneMethod.STRYD_RUNNING
        
    def get_method_description(self) -> str:
        return "Stryd 5-zone running power system based on official Stryd Powercenter zones"


class CriticalPowerCalculator(PowerZoneCalculator):
    """
    Critical Power Model Zone Calculator
    
    Based on the Critical Power model which uses CP and W' (W-prime)
    to define sustainable and finite work capacity
    """
    
    def __init__(self, w_prime: Optional[float] = None):
        """
        Initialize Critical Power calculator
        
        Args:
            w_prime: W' (anaerobic work capacity) in kilojoules
        """
        self.w_prime = w_prime
    
    def calculate_zones(self, threshold_power: float, body_weight: Optional[float] = None) -> List[PowerZone]:
        """Calculate zones based on Critical Power model"""
        if threshold_power <= 0:
            raise InvalidParameterError("Critical power must be positive")
        
        # If W' is not provided, estimate it (typical range 15-25 kJ)
        if self.w_prime is None:
            self.w_prime = 20.0  # Default estimate of 20 kJ
            
        zones = [
            PowerZone(
                zone_number=1,
                zone_name="Recovery",
                power_range=(threshold_power * 0.0, threshold_power * 0.60),
                percentage_range=(0, 60),
                description="Below aerobic threshold, recovery efforts",
                purpose="Active recovery, aerobic base maintenance",
                physiological_adaptations="Enhanced recovery, fat oxidation",
                duration_guidance="Unlimited duration sustainable",
                effort_level="Very easy"
            ),
            PowerZone(
                zone_number=2,
                zone_name="Aerobic",
                power_range=(threshold_power * 0.60, threshold_power * 0.80),
                percentage_range=(60, 80),
                description="Aerobic base training, well below CP",
                purpose="Aerobic development, base building",
                physiological_adaptations="Mitochondrial adaptations, capillarization",
                duration_guidance="Several hours sustainable",
                effort_level="Easy, conversational"
            ),
            PowerZone(
                zone_number=3,
                zone_name="Extensive Endurance",
                power_range=(threshold_power * 0.80, threshold_power * 0.90),
                percentage_range=(80, 90),
                description="Moderate aerobic intensity, below CP",
                purpose="Aerobic capacity, endurance development",
                physiological_adaptations="Improved aerobic power, efficiency",
                duration_guidance="1-4 hours sustainable",
                effort_level="Moderate"
            ),
            PowerZone(
                zone_number=4,
                zone_name="Intensive Endurance",
                power_range=(threshold_power * 0.90, threshold_power * 1.00),
                percentage_range=(90, 100),
                description="Near Critical Power, high-end aerobic",
                purpose="CP development, lactate steady state",
                physiological_adaptations="Enhanced lactate clearance, CP improvement",
                duration_guidance="30-90 minutes sustainable",
                effort_level="Hard but steady"
            ),
            PowerZone(
                zone_number=5,
                zone_name="Critical Power",
                power_range=(threshold_power * 1.00, threshold_power * 1.05),
                percentage_range=(100, 105),
                description="At or slightly above Critical Power",
                purpose="CP training, lactate threshold work",
                physiological_adaptations="CP improvement, metabolic adaptations",
                duration_guidance="20-60 minutes depending on intensity",
                effort_level="Hard, sustainable with focus"
            ),
            PowerZone(
                zone_number=6,
                zone_name="W' Depletion",
                power_range=(threshold_power * 1.05, threshold_power * 1.30),
                percentage_range=(105, 130),
                description="Above CP, drawing on W' (anaerobic reserve)",
                purpose="W' development, lactate tolerance",
                physiological_adaptations="Improved anaerobic capacity, W' expansion",
                duration_guidance="Duration depends on W' depletion rate",
                effort_level="Very hard, time-limited"
            ),
            PowerZone(
                zone_number=7,
                zone_name="Maximal Power",
                power_range=(threshold_power * 1.30, threshold_power * 3.00),
                percentage_range=(130, 300),
                description="High W' depletion rate, sprint power",
                purpose="Peak power, neuromuscular development",
                physiological_adaptations="Neuromuscular power, sprint capacity",
                duration_guidance="Seconds to few minutes maximum",
                effort_level="Maximum to near-maximum"
            )
        ]
        
        logger.info(f"Calculated Critical Power zones for CP: {threshold_power}W, W': {self.w_prime}kJ")
        return zones
    
    def get_method_name(self) -> PowerZoneMethod:
        return PowerZoneMethod.CRITICAL_POWER
        
    def get_method_description(self) -> str:
        return "Critical Power model zones based on CP and W' (anaerobic work capacity)"


class PowerZoneAnalyzer(FitnessAnalyzer):
    """Power zone analysis and calculation engine"""
    
    def __init__(self):
        super().__init__()
        self._calculators = {
            PowerZoneMethod.STEVE_PALLADINO: StevePalladinoCalculator(),
            PowerZoneMethod.STRYD_RUNNING: StrydRunningCalculator(), 
            PowerZoneMethod.CRITICAL_POWER: CriticalPowerCalculator()
        }
    
    def calculate_power_zones(
        self, 
        threshold_power: float,
        method: PowerZoneMethod = PowerZoneMethod.STEVE_PALLADINO,
        body_weight: Optional[float] = None,
        w_prime: Optional[float] = None
    ) -> PowerZoneResult:
        """
        Calculate power zones using specified method
        
        Args:
            threshold_power: FTP or Critical Power in watts
            method: Power zone calculation method
            body_weight: Body weight in kg (optional)
            w_prime: W' for Critical Power method (kJ)
            
        Returns:
            PowerZoneResult with calculated zones
        """
        if threshold_power <= 0:
            raise InvalidParameterError("Threshold power must be positive")
            
        # Handle Critical Power method with W' parameter
        if method == PowerZoneMethod.CRITICAL_POWER and w_prime is not None:
            calculator = CriticalPowerCalculator(w_prime)
        else:
            calculator = self._calculators.get(method)
            
        if not calculator:
            raise InvalidParameterError(f"Unsupported power zone method: {method}")
        
        zones = calculator.calculate_zones(threshold_power, body_weight)
        
        # Calculate normalized power (W/kg) if body weight provided
        normalized_power = threshold_power / body_weight if body_weight else threshold_power
        
        metadata = {
            "method_description": calculator.get_method_description(),
            "calculation_timestamp": datetime.utcnow().isoformat(),
            "body_weight": body_weight,
            "normalized_power_w_per_kg": normalized_power if body_weight else None
        }
        
        if method == PowerZoneMethod.CRITICAL_POWER:
            metadata["w_prime_kj"] = getattr(calculator, 'w_prime', None)
        
        result = PowerZoneResult(
            method=method,
            zones=zones,
            threshold_power=threshold_power,
            normalized_power=normalized_power,
            calculation_metadata=metadata,
            timestamp=datetime.utcnow(),
            analytics_type=AnalyticsType.POWER_ANALYSIS
        )
        
        logger.info(f"Calculated {len(zones)} power zones using {method.value} method")
        return result
    
    def analyze(self, data: Dict[str, Any], filters: AnalyticsFilter) -> AnalyticsResult:
        """
        Analyze power data and calculate zones
        
        Args:
            data: Dictionary containing power data and parameters
            filters: Analytics filters and parameters
            
        Returns:
            PowerZoneResult
        """
        threshold_power = data.get("threshold_power")
        if not threshold_power:
            raise InvalidParameterError("Threshold power is required for power zone analysis")
            
        method = PowerZoneMethod(data.get("method", "steve_palladino"))
        body_weight = data.get("body_weight")
        w_prime = data.get("w_prime")
        
        return self.calculate_power_zones(threshold_power, method, body_weight, w_prime)
    
    def get_supported_methods(self) -> List[PowerZoneMethod]:
        """Return list of supported power zone calculation methods"""
        return list(self._calculators.keys())
    
    def get_method_description(self, method: PowerZoneMethod) -> str:
        """Get description of a specific power zone method"""
        calculator = self._calculators.get(method)
        if not calculator:
            raise InvalidParameterError(f"Unsupported method: {method}")
        return calculator.get_method_description()

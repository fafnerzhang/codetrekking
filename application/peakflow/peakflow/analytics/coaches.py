"""
Coaching methodology models and data.

This module defines structured coaching profiles including training philosophies,
workout structures, and training phase principles from renowned endurance coaches.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class CoachingStyle(str, Enum):
    """Primary coaching philosophy approach."""
    PERIODIZATION = "periodization"
    ADAPTIVE = "adaptive"
    HIGH_VOLUME = "high_volume"
    LACTATE_THRESHOLD = "lactate_threshold"
    CUMULATIVE_FATIGUE = "cumulative_fatigue"


class WorkoutStructure(str, Enum):
    """Preferred workout organization pattern."""
    MICROCYCLE = "microcycle"
    BLOCK_PERIODIZATION = "block_periodization"
    PYRAMID = "pyramid"
    PROGRESSIVE_INTERVALS = "progressive_intervals"


class TrainingPhase(BaseModel):
    """Training phase characteristics and principles."""
    name: str = Field(..., description="Phase name (e.g., Base, Build, Peak)")
    duration_weeks: str = Field(..., description="Typical duration range")
    focus: str = Field(..., description="Primary training focus")
    intensity_distribution: str = Field(..., description="Intensity distribution pattern")
    key_workouts: List[str] = Field(..., description="Characteristic workout types")


class CoachProfile(BaseModel):
    """Complete coaching methodology profile."""
    id: str = Field(..., description="Unique coach identifier")
    name: str = Field(..., description="Coach name")
    primary_style: CoachingStyle = Field(..., description="Primary coaching philosophy")
    sport_focus: List[str] = Field(..., description="Sports specialization")

    history: str = Field(..., description="Coach background and experience")
    expertise: List[str] = Field(..., description="Areas of expertise")

    coaching_philosophy: str = Field(..., description="Core training philosophy")
    workout_structure_preference: WorkoutStructure = Field(..., description="Preferred workout organization")

    training_phases: List[TrainingPhase] = Field(..., description="Training phase structure")

    key_principles: List[str] = Field(..., description="Fundamental training principles")
    notable_athletes: Optional[List[str]] = Field(default=None, description="Notable coached athletes")
    publications: Optional[List[str]] = Field(default=None, description="Books and publications")


# Static coach database
COACHES = [
    CoachProfile(
        id="joe_friel",
        name="Joe Friel",
        primary_style=CoachingStyle.PERIODIZATION,
        sport_focus=["running", "triathlon"],

        history="Created the Training Bible series and pioneered the application of periodization "
                "to endurance sports. Founded TrainingPeaks and revolutionized data-driven training. "
                "Applied classic periodization principles to running and multi-sport endurance training.",

        expertise=[
            "Classic periodization theory",
            "Race-specific fitness building",
            "Threshold-based training",
            "Age-group athlete optimization",
            "Annual training planning"
        ],

        coaching_philosophy="Training should be periodized into distinct phases with specific physiological "
                           "adaptations. Focus on building limiters while maintaining strengths. "
                           "Use Annual Training Plan (ATP) to structure the season around goal races.",

        workout_structure_preference=WorkoutStructure.MICROCYCLE,

        training_phases=[
            TrainingPhase(
                name="Base",
                duration_weeks="8-12 weeks",
                focus="Aerobic endurance, muscular endurance, speed skills",
                intensity_distribution="80% Zone 1-2, 20% Zone 3-4",
                key_workouts=["Long runs", "Tempo runs", "Hill repeats", "Strides"]
            ),
            TrainingPhase(
                name="Build",
                duration_weeks="8-12 weeks",
                focus="Lactate threshold, VO2max, race-specific intensity",
                intensity_distribution="70% Zone 1-2, 30% Zone 4-5",
                key_workouts=["Threshold intervals", "VO2max repeats", "Race-pace runs", "Cruise intervals"]
            ),
            TrainingPhase(
                name="Peak",
                duration_weeks="2-4 weeks",
                focus="Maintain fitness, sharpen race-specific abilities",
                intensity_distribution="60% Zone 1-2, 40% Zone 4-6",
                key_workouts=["Short high-intensity intervals", "Race-pace efforts", "Tune-up races"]
            ),
            TrainingPhase(
                name="Race",
                duration_weeks="1-4 weeks",
                focus="Taper and compete",
                intensity_distribution="50% Zone 1-2, 50% race intensity",
                key_workouts=["Race events", "Short openers", "Easy recovery runs"]
            ),
            TrainingPhase(
                name="Transition",
                duration_weeks="1-4 weeks",
                focus="Physical and mental recovery",
                intensity_distribution="100% Zone 1-2",
                key_workouts=["Easy aerobic exercise", "Cross-training", "Active recovery"]
            )
        ],

        key_principles=[
            "Train your limiters in the Build period",
            "Maintain your strengths with minimal training",
            "Progressive overload with strategic recovery weeks",
            "Race-specific training increases as event approaches",
            "Use CTL/ATL/TSB (PMC) to manage training load",
            "Identify and address individual limiters (endurance, threshold, speed)"
        ],

        notable_athletes=["Multiple age-group national and world champions"],

        publications=[
            "The Runner's Training Bible",
            "The Triathlete's Training Bible",
            "Fast After 50",
            "Going Long (with Gordon Byrn)"
        ]
    ),

    CoachProfile(
        id="brad_hudson",
        name="Brad Hudson",
        primary_style=CoachingStyle.ADAPTIVE,
        sport_focus=["running", "marathon"],

        history="Elite distance running coach known for adaptive, individualized training methods. "
                "Coached Olympic Trials qualifiers and professional runners. Emphasizes listening "
                "to the body and adjusting training based on response.",

        expertise=[
            "Adaptive training response",
            "Marathon-specific preparation",
            "Medium-long run emphasis",
            "Situational tempo runs"
        ],

        coaching_philosophy="Training must be adaptive to individual response. Use medium-long runs "
                           "as the training foundation. Vary workout structure based on athlete feedback. "
                           "Build aerobic strength through consistent moderate-hard efforts rather than "
                           "rigid periodization.",

        workout_structure_preference=WorkoutStructure.PROGRESSIVE_INTERVALS,

        training_phases=[
            TrainingPhase(
                name="Foundation",
                duration_weeks="6-8 weeks",
                focus="Aerobic base building, running economy",
                intensity_distribution="75% easy, 15% moderate, 10% hard",
                key_workouts=["Long runs", "Medium-long runs", "Easy running", "Strides"]
            ),
            TrainingPhase(
                name="Fundamental",
                duration_weeks="4-6 weeks",
                focus="Aerobic strength, lactate threshold development",
                intensity_distribution="70% easy, 20% moderate, 10% hard",
                key_workouts=["Long runs with surges", "Tempo runs", "Medium-long runs", "Hill circuits"]
            ),
            TrainingPhase(
                name="Sharpening",
                duration_weeks="8-10 weeks",
                focus="Race-specific fitness, VO2max, speed",
                intensity_distribution="65% easy, 20% moderate, 15% hard",
                key_workouts=["Marathon-pace long runs", "VO2max intervals", "Situational tempo", "Time trials"]
            ),
            TrainingPhase(
                name="Taper",
                duration_weeks="2-3 weeks",
                focus="Recovery while maintaining sharpness",
                intensity_distribution="80% easy, 10% moderate, 10% hard",
                key_workouts=["Short tempo runs", "Race-pace intervals", "Easy running"]
            )
        ],

        key_principles=[
            "Medium-long runs (12-16 miles) are the training foundation",
            "Situational tempo runs adapt to terrain and conditions",
            "Long runs with progressive pace or surges build marathon fitness",
            "Listen to your body and adjust daily training accordingly",
            "Consistency over intensity in base training",
            "Use uphill and downhill running for strength and economy"
        ],

        notable_athletes=[
            "Dathan Ritzenhein",
            "Becky Wade",
            "Jorge Torres",
            "Sara Slattery"
        ],

        publications=[
            "Run Faster from the 5K to the Marathon"
        ]
    ),

    CoachProfile(
        id="jack_daniels",
        name="Jack Daniels",
        primary_style=CoachingStyle.LACTATE_THRESHOLD,
        sport_focus=["running", "middle_distance", "distance"],

        history="Olympic medalist, exercise physiologist, and legendary running coach. Created "
                "the VDOT system for training intensity calibration. Coached multiple NCAA champions "
                "and Olympic athletes over 60+ years.",

        expertise=[
            "Exercise physiology",
            "VDOT training intensity system",
            "Scientific periodization",
            "Training intensity zones"
        ],

        coaching_philosophy="Training must have a specific purpose tied to measurable physiological "
                           "adaptations. Use VDOT to prescribe precise training paces. Balance training "
                           "stress across Easy, Marathon, Threshold, Interval, and Repetition paces. "
                           "Quality over quantity - every run has a specific purpose.",

        workout_structure_preference=WorkoutStructure.PYRAMID,

        training_phases=[
            TrainingPhase(
                name="Phase I - Foundation",
                duration_weeks="6 weeks minimum",
                focus="Aerobic development, injury prevention",
                intensity_distribution="100% Easy pace",
                key_workouts=["Easy runs", "Long runs", "Strides"]
            ),
            TrainingPhase(
                name="Phase II - Early Quality",
                duration_weeks="6 weeks",
                focus="Lactate threshold, aerobic capacity introduction",
                intensity_distribution="80% Easy, 10% Threshold, 10% Interval",
                key_workouts=["Threshold runs (T)", "Cruise intervals", "Easy runs", "Long runs"]
            ),
            TrainingPhase(
                name="Phase III - Advanced Quality",
                duration_weeks="6 weeks",
                focus="VO2max development, race-specific speed",
                intensity_distribution="70% Easy, 15% Threshold, 10% Interval, 5% Repetition",
                key_workouts=["Interval workouts (I)", "Threshold runs", "Repetition intervals (R)", "Long runs"]
            ),
            TrainingPhase(
                name="Phase IV - Race Preparation",
                duration_weeks="Up to race",
                focus="Race-specific fitness, maintaining adaptations",
                intensity_distribution="65% Easy, 15% Marathon/Threshold, 15% Interval, 5% Repetition",
                key_workouts=["Marathon-pace runs (M)", "Race-pace intervals", "Threshold runs", "Tune-up races"]
            )
        ],

        key_principles=[
            "Every training intensity targets a specific physiological system",
            "VDOT determines all training paces based on current fitness",
            "Easy runs for recovery and aerobic development (59-74% VO2max)",
            "Marathon pace for race-specific endurance (80-90% VO2max)",
            "Threshold pace for lactate clearance improvement (83-88% VO2max)",
            "Interval pace for VO2max development (95-100% VO2max)",
            "Repetition pace for speed and economy (105-120% VO2max)",
            "Training stress limited to avoid injury: no more than 10% quality per week",
            "Long runs should not exceed 25% weekly mileage or 150 minutes"
        ],

        notable_athletes=[
            "Jim Ryun",
            "Ken Martin",
            "Multiple NCAA champions at SUNY Cortland and Notre Dame"
        ],

        publications=[
            "Daniels' Running Formula",
            "Running Science (co-author)"
        ]
    ),

    CoachProfile(
        id="hansons",
        name="Hanson's Method",
        primary_style=CoachingStyle.CUMULATIVE_FATIGUE,
        sport_focus=["marathon"],

        history="Developed by brothers Keith and Kevin Hanson for the Hanson-Brooks Distance Project. "
                "Built on the principle of cumulative fatigue to simulate marathon conditions. "
                "Coached multiple Olympic Marathon Trials qualifiers and professional marathoners.",

        expertise=[
            "Cumulative fatigue training",
            "Marathon-specific adaptation",
            "High-frequency moderate volume",
            "Something of Substance (SOS) workouts"
        ],

        coaching_philosophy="Train tired to race fresh. Use cumulative fatigue from frequent hard efforts "
                           "to simulate marathon conditions. Cap long runs at 16 miles - the cumulative "
                           "fatigue from the training week provides marathon-specific adaptations without "
                           "excessive single-session damage. Three 'Something of Substance' (SOS) workouts "
                           "per week develop all necessary systems.",

        workout_structure_preference=WorkoutStructure.MICROCYCLE,

        training_phases=[
            TrainingPhase(
                name="Base Building",
                duration_weeks="10 weeks",
                focus="Aerobic foundation, volume accumulation",
                intensity_distribution="90% easy, 10% moderate",
                key_workouts=["Easy runs 6 days/week", "Progressive long runs", "Tempo introductions"]
            ),
            TrainingPhase(
                name="Strength Phase",
                duration_weeks="6 weeks",
                focus="Lactate threshold, strength endurance",
                intensity_distribution="75% easy, 20% threshold, 5% speed",
                key_workouts=["Tempo runs", "Speed workouts", "Long runs", "3 SOS days per week"]
            ),
            TrainingPhase(
                name="Peak Phase",
                duration_weeks="3 weeks",
                focus="Marathon-pace work, cumulative fatigue simulation",
                intensity_distribution="70% easy, 25% marathon pace, 5% speed",
                key_workouts=["16-mile long runs", "10-mile marathon-pace runs", "Speed workouts", "Tempo runs"]
            ),
            TrainingPhase(
                name="Taper",
                duration_weeks="10 days",
                focus="Recovery and sharpening",
                intensity_distribution="80% easy, 15% marathon pace, 5% speed",
                key_workouts=["Reduced volume SOS workouts", "Easy runs", "Short marathon-pace segments"]
            )
        ],

        key_principles=[
            "Cap long runs at 16 miles - cumulative fatigue provides marathon adaptation",
            "Three SOS (Something of Substance) workouts per week",
            "Train tired to simulate marathon fatigue conditions",
            "6 days per week running minimum for cumulative effect",
            "Strength Phase: build lactate threshold capacity",
            "Peak Phase: marathon-pace work under cumulative fatigue",
            "10-day taper (shorter than traditional methods)",
            "Moderate volume (55-70 mpw) with high frequency",
            "Every run serves a specific purpose - no junk miles"
        ],

        notable_athletes=[
            "Brian Sell (2:10 marathoner, Olympic Trials winner)",
            "Desiree Linden (Boston Marathon champion)",
            "Multiple Hanson-Brooks Distance Project athletes"
        ],

        publications=[
            "Hansons Marathon Method",
            "Hansons Half-Marathon Method",
            "Hansons First Marathon"
        ]
    )
]


def get_all_coaches() -> List[CoachProfile]:
    """Return all coach profiles."""
    return COACHES


def get_coach_by_id(coach_id: str) -> Optional[CoachProfile]:
    """Get specific coach profile by ID."""
    for coach in COACHES:
        if coach.id == coach_id:
            return coach
    return None

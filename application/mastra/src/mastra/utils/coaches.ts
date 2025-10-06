/**
 * Coaching methodology profiles and instructions generator
 *
 * LLM-friendly coaching profiles with structured, actionable guidance.
 * Each coach profile contains clear principles, phase structures, and
 * decision-making frameworks for training plan generation.
 */

import { RuntimeContext } from '@mastra/core/runtime-context';

export enum CoachingStyle {
  PERIODIZATION = "periodization",
  ADAPTIVE = "adaptive",
  HIGH_VOLUME = "high_volume",
  LACTATE_THRESHOLD = "lactate_threshold",
  CUMULATIVE_FATIGUE = "cumulative_fatigue"
}

export enum WorkoutStructure {
  MICROCYCLE = "microcycle",
  BLOCK_PERIODIZATION = "block_periodization",
  PYRAMID = "pyramid",
  PROGRESSIVE_INTERVALS = "progressive_intervals"
}

export interface IntensityGuidelines {
  easy: string;
  moderate: string;
  hard: string;
  recovery_week_adjustment: string;
}

export interface TrainingPhase {
  name: string;
  tag: string; // Short identifier like 'base', 'build', 'peak', 'taper'
  duration_weeks: string;
  primary_goals: string[];
  intensity_distribution: IntensityGuidelines;
  weekly_structure: string;
  key_workouts: Array<{
    name: string;
    purpose: string;
    frequency: string; // e.g., "1x per week", "2x per week"
  }>;
  progression_strategy: string;
}

export interface DecisionFramework {
  when_to_use: string[];
  avoid_if: string[];
  ideal_for: string[];
}

export interface CoachProfile {
  id: string;
  name: string;
  primary_style: CoachingStyle;
  sport_focus: string[];

  // Core philosophy - concise and actionable
  philosophy_summary: string;
  core_beliefs: string[];

  // Training phase templates
  training_phases: TrainingPhase[];

  // Key coaching rules
  key_principles: string[];

  // Decision-making guidance
  decision_framework: DecisionFramework;

  // Workout structure preference
  workout_structure_preference: WorkoutStructure;
  workout_design_rules: string[];

  // Additional context (optional)
  notable_achievements?: string[];
  signature_workouts?: Array<{
    name: string;
    description: string;
  }>;
}

// Static coach database
export const COACHES: CoachProfile[] = [
  {
    id: "joe_friel",
    name: "Joe Friel",
    primary_style: CoachingStyle.PERIODIZATION,
    sport_focus: ["running", "triathlon", "cycling"],

    philosophy_summary: "Classic periodization with distinct training phases. Build limiters, maintain strengths, and peak for goal races using structured Annual Training Plan.",

    core_beliefs: [
      "Every training phase has a specific physiological purpose",
      "Train weaknesses (limiters) while maintaining strengths with minimal work",
      "Progressive overload requires strategic recovery weeks (3:1 or 2:1 ratio)",
      "Race-specific training intensity increases as goal event approaches",
      "Data-driven training load management using CTL/ATL/TSB metrics"
    ],

    training_phases: [
      {
        name: "Base Building",
        tag: "base",
        duration_weeks: "8-12 weeks",
        primary_goals: [
          "Build aerobic endurance foundation",
          "Develop muscular endurance",
          "Establish consistent volume tolerance",
          "Perfect running economy and form"
        ],
        intensity_distribution: {
          easy: "80% of weekly volume in Zone 1-2 (conversational pace)",
          moderate: "15% in Zone 3 (tempo pace)",
          hard: "5% in Zone 4 (threshold pace)",
          recovery_week_adjustment: "Reduce volume by 20-30%, maintain some intensity"
        },
        weekly_structure: "5-6 days running. 1 long run, 1 tempo run, 1 hill session, 3-4 easy runs, 1 rest day",
        key_workouts: [
          { name: "Long Run", purpose: "Build aerobic endurance and time on feet", frequency: "1x per week" },
          { name: "Tempo Run", purpose: "Develop aerobic capacity at upper Zone 2/low Zone 3", frequency: "1x per week" },
          { name: "Hill Repeats", purpose: "Build muscular endurance and running power", frequency: "1x per week" },
          { name: "Strides", purpose: "Maintain speed skills and running economy", frequency: "2-3x per week after easy runs" }
        ],
        progression_strategy: "Increase volume by 5-10% per week. Every 3-4 weeks, insert recovery week with 20-30% volume reduction."
      },
      {
        name: "Build/Specific Preparation",
        tag: "build",
        duration_weeks: "8-12 weeks",
        primary_goals: [
          "Raise lactate threshold",
          "Develop VO2max capacity",
          "Train race-specific intensities",
          "Address individual limiters"
        ],
        intensity_distribution: {
          easy: "70% of volume in Zone 1-2",
          moderate: "15% in Zone 3-4 (threshold work)",
          hard: "15% in Zone 5 (VO2max intervals)",
          recovery_week_adjustment: "Reduce volume by 30%, keep 1 intensity session"
        },
        weekly_structure: "5-6 days running. 1 long run, 2 quality sessions (threshold + intervals), 3-4 easy/recovery runs",
        key_workouts: [
          { name: "Threshold Intervals", purpose: "Raise lactate threshold and sustainable pace", frequency: "1x per week" },
          { name: "VO2max Repeats", purpose: "Develop maximum aerobic capacity", frequency: "1x per week" },
          { name: "Race-Pace Runs", purpose: "Practice goal race intensity", frequency: "1x every 2 weeks" },
          { name: "Cruise Intervals", purpose: "Threshold work with short recovery", frequency: "Alternate with tempo" }
        ],
        progression_strategy: "Maintain or slightly increase volume. Increase intensity/duration of quality sessions by 5-10% per week. Recovery weeks every 3-4 weeks."
      },
      {
        name: "Peak/Sharpening",
        tag: "peak",
        duration_weeks: "2-4 weeks",
        primary_goals: [
          "Sharpen race-specific fitness",
          "Maintain fitness while reducing fatigue",
          "Fine-tune pacing and mental preparation"
        ],
        intensity_distribution: {
          easy: "60% in Zone 1-2",
          moderate: "20% in Zone 3-4",
          hard: "20% in Zone 5-6 (race pace and faster)",
          recovery_week_adjustment: "N/A - entire phase is controlled volume reduction"
        },
        weekly_structure: "4-5 days running. Reduce volume by 20-40%. Maintain intensity but reduce duration of hard sessions.",
        key_workouts: [
          { name: "Short High-Intensity Intervals", purpose: "Maintain top-end speed and power", frequency: "1x per week" },
          { name: "Race-Pace Efforts", purpose: "Dial in goal race pace", frequency: "1x per week" },
          { name: "Tune-Up Race", purpose: "Practice race execution at shorter distance", frequency: "Optional, 2-3 weeks before goal race" }
        ],
        progression_strategy: "Progressive volume reduction. Keep intensity high but reduce duration. Focus on freshness over fitness."
      },
      {
        name: "Race/Taper",
        tag: "race",
        duration_weeks: "1-2 weeks",
        primary_goals: [
          "Maximize race-day freshness",
          "Maintain neuromuscular readiness",
          "Complete mental preparation"
        ],
        intensity_distribution: {
          easy: "50% very easy running",
          moderate: "25% moderate intensity",
          hard: "25% short race-intensity efforts",
          recovery_week_adjustment: "N/A - taper protocol"
        },
        weekly_structure: "3-4 days running maximum. Very low volume. Short, sharp sessions to maintain readiness.",
        key_workouts: [
          { name: "Race Event", purpose: "Execute race plan", frequency: "1x (race day)" },
          { name: "Short Openers", purpose: "Maintain neuromuscular activation", frequency: "2-3x in week before race" },
          { name: "Easy Recovery Runs", purpose: "Active recovery and mental relaxation", frequency: "As needed, all very short" }
        ],
        progression_strategy: "Volume reduced by 40-60% in final week. Last hard workout 3-5 days before race. Short strides day before race."
      },
      {
        name: "Transition/Recovery",
        tag: "transition",
        duration_weeks: "1-4 weeks",
        primary_goals: [
          "Physical recovery from training cycle",
          "Mental break from structured training",
          "Maintain basic aerobic fitness"
        ],
        intensity_distribution: {
          easy: "100% in Zone 1-2",
          moderate: "0%",
          hard: "0%",
          recovery_week_adjustment: "N/A - entire phase is recovery"
        },
        weekly_structure: "Unstructured. Focus on enjoyment and recovery. No intensity.",
        key_workouts: [
          { name: "Easy Aerobic Running", purpose: "Maintain aerobic base without stress", frequency: "As desired, no schedule" },
          { name: "Cross-Training", purpose: "Active recovery with different movement patterns", frequency: "Optional, for enjoyment" },
          { name: "Complete Rest", purpose: "Physical and mental recovery", frequency: "As needed" }
        ],
        progression_strategy: "No progression. Listen to body. Resume structured training when mentally refreshed."
      }
    ],

    key_principles: [
      "Identify your three limiters: endurance, threshold, or speed - focus training on weakest areas",
      "Use 3:1 or 2:1 loading pattern (3 build weeks : 1 recovery week)",
      "Maintain strengths with minimal training volume to focus energy on limiters",
      "Plan entire season backward from goal A-priority race",
      "Monitor CTL (fitness), ATL (fatigue), and TSB (form) to manage training load scientifically",
      "Base phase builds foundation - never skip or rush this phase",
      "Each training phase must match the athlete's current fitness and race goals"
    ],

    decision_framework: {
      when_to_use: [
        "Athlete has 16+ weeks until goal race (ideal for full periodization)",
        "Training for specific race distance and date",
        "Athlete responds well to structured, planned training",
        "Goal is peak performance on specific date",
        "Athlete has clear limiters to address"
      ],
      avoid_if: [
        "Less than 12 weeks to race (insufficient time for full periodization)",
        "Athlete prefers intuitive/feel-based training",
        "Multiple A-priority races close together",
        "Athlete has injury history requiring more adaptive approach"
      ],
      ideal_for: [
        "Marathon and half-marathon preparation",
        "Age-group athletes aiming for PRs",
        "Athletes with specific performance goals",
        "Structured personalities who thrive on planning",
        "First-time race distance attempts"
      ]
    },

    workout_structure_preference: WorkoutStructure.MICROCYCLE,

    workout_design_rules: [
      "Every workout must have a specific physiological purpose - no junk miles",
      "Recovery runs should be truly easy (Zone 1-2, conversational)",
      "Quality sessions need 48 hours recovery minimum",
      "Long runs should not exceed 20-25% of weekly volume",
      "Warm-up and cool-down are non-negotiable for quality sessions",
      "Hard days hard, easy days easy - avoid moderate/gray zone training"
    ],

    notable_achievements: [
      "Authored The Training Bible series (cycling, triathlon, running)",
      "Founded TrainingPeaks platform for data-driven training",
      "Coached multiple age-group world champions",
      "Pioneered Training Stress Score (TSS) methodology"
    ],

    signature_workouts: [
      {
        name: "Cruise Intervals",
        description: "Threshold-pace intervals (10-20 min) with short recovery (1-2 min). Builds lactate clearance capacity."
      },
      {
        name: "Tempo Run",
        description: "Sustained effort at upper Zone 2/low Zone 3 (20-40 min). Develops aerobic capacity and mental toughness."
      },
      {
        name: "Hill Repeats",
        description: "Short-to-medium hill climbs (30 sec - 3 min) with jog-down recovery. Builds power and muscular endurance."
      }
    ]
  },

  {
    id: "brad_hudson",
    name: "Brad Hudson",
    primary_style: CoachingStyle.ADAPTIVE,
    sport_focus: ["running", "marathon", "distance"],

    philosophy_summary: "Adaptive training based on individual response. Medium-long runs as foundation. Flexible workout structure adjusted to athlete feedback and recovery status.",

    core_beliefs: [
      "Training must adapt to how the athlete responds - no rigid schedules",
      "Medium-long runs (12-16 miles) are more valuable than classic long runs for marathoners",
      "Build aerobic strength through consistent moderate-hard efforts",
      "Situational tempo runs adapt to terrain, weather, and athlete readiness",
      "Consistency over intensity - avoid injury by listening to body signals"
    ],

    training_phases: [
      {
        name: "Foundation Phase",
        tag: "foundation",
        duration_weeks: "6-8 weeks",
        primary_goals: [
          "Build aerobic base through volume accumulation",
          "Develop running economy and efficiency",
          "Establish medium-long run tolerance",
          "Create consistent training rhythm"
        ],
        intensity_distribution: {
          easy: "75% of volume at easy conversational pace",
          moderate: "15% at steady/moderate effort",
          hard: "10% at hard effort (strides, short hills)",
          recovery_week_adjustment: "Reduce volume by 25%, keep some moderate work"
        },
        weekly_structure: "6-7 days running. Emphasize medium-long runs (12-16 miles). Include 1-2 long runs and frequent easy running with strides.",
        key_workouts: [
          { name: "Medium-Long Run", purpose: "Build aerobic strength without excessive fatigue", frequency: "2-3x per week" },
          { name: "Long Run", purpose: "Develop endurance and mental toughness", frequency: "1x per week" },
          { name: "Easy Running with Strides", purpose: "Active recovery plus speed skills", frequency: "3-4x per week" },
          { name: "General Aerobic Run", purpose: "Volume accumulation at comfortable pace", frequency: "Daily except rest day" }
        ],
        progression_strategy: "Gradually increase frequency of medium-long runs. Build volume conservatively. Focus on consistency over dramatic increases."
      },
      {
        name: "Fundamental Phase",
        tag: "fundamental",
        duration_weeks: "4-6 weeks",
        primary_goals: [
          "Develop aerobic strength at moderate intensity",
          "Introduce lactate threshold work",
          "Build resilience through varied terrain",
          "Maintain high training frequency"
        ],
        intensity_distribution: {
          easy: "70% easy running",
          moderate: "20% moderate/tempo effort",
          hard: "10% hard effort (hills, surges)",
          recovery_week_adjustment: "Reduce volume, keep 1 quality session lighter"
        },
        weekly_structure: "6-7 days running. Medium-long runs continue. Add tempo runs and long runs with surges. Hill circuits for strength.",
        key_workouts: [
          { name: "Long Run with Surges", purpose: "Simulate marathon fatigue and pace changes", frequency: "1x every 10-14 days" },
          { name: "Situational Tempo Run", purpose: "Threshold work adapted to terrain and conditions", frequency: "1x per week" },
          { name: "Medium-Long Run", purpose: "Continue building aerobic strength", frequency: "2x per week" },
          { name: "Hill Circuits", purpose: "Build strength and power without track intervals", frequency: "1x per week" }
        ],
        progression_strategy: "Introduce quality sessions gradually. Adjust tempo run structure based on how athlete feels. Use hills and surges instead of rigid track work."
      },
      {
        name: "Sharpening Phase",
        tag: "sharpening",
        duration_weeks: "8-10 weeks",
        primary_goals: [
          "Develop race-specific marathon fitness",
          "Raise VO2max ceiling",
          "Practice goal marathon pace",
          "Sharpen speed while maintaining volume"
        ],
        intensity_distribution: {
          easy: "65% easy running",
          moderate: "20% moderate/marathon pace",
          hard: "15% hard/VO2max effort",
          recovery_week_adjustment: "Reduce volume by 20%, keep intensity sharp but shorter"
        },
        weekly_structure: "6-7 days running. Marathon-pace long runs. VO2max intervals. Situational tempo. Medium-long runs continue.",
        key_workouts: [
          { name: "Marathon-Pace Long Run", purpose: "Practice goal pace under fatigue", frequency: "1x every 2 weeks" },
          { name: "VO2max Intervals", purpose: "Raise aerobic ceiling", frequency: "1x per week" },
          { name: "Situational Tempo", purpose: "Adaptive threshold work based on conditions", frequency: "1x per week" },
          { name: "Time Trial or Tune-Up Race", purpose: "Assess fitness and practice racing", frequency: "Optional, every 3-4 weeks" }
        ],
        progression_strategy: "Progressive increase in marathon-pace running. VO2max work increases in volume. Adapt all sessions to athlete response - no forced workouts."
      },
      {
        name: "Taper Phase",
        tag: "taper",
        duration_weeks: "2-3 weeks",
        primary_goals: [
          "Recover from training cycle while maintaining fitness",
          "Sharpen neuromuscular system",
          "Mental preparation and confidence building"
        ],
        intensity_distribution: {
          easy: "80% very easy running",
          moderate: "10% moderate effort",
          hard: "10% short race-pace work",
          recovery_week_adjustment: "N/A - entire phase is controlled taper"
        },
        weekly_structure: "4-5 days running. Significant volume reduction. Maintain some intensity but very short duration.",
        key_workouts: [
          { name: "Short Tempo Run", purpose: "Maintain threshold fitness without fatigue", frequency: "1x in first week of taper" },
          { name: "Race-Pace Intervals", purpose: "Dial in goal pace, build confidence", frequency: "1-2x, ending 5-7 days before race" },
          { name: "Easy Running", purpose: "Active recovery and mental relaxation", frequency: "Short, frequent runs" }
        ],
        progression_strategy: "Reduce volume by 30-50%. Keep legs fresh. Last quality session 5-7 days before race. Short strides day before race."
      }
    ],

    key_principles: [
      "Medium-long runs (12-16 miles) build marathon fitness more effectively than very long runs alone",
      "Adapt every workout to current conditions: terrain, weather, and athlete readiness",
      "Long runs with progressive pace or surges prepare for marathon-specific fatigue",
      "Listen to body signals daily - adjust or skip workouts when needed",
      "Consistency over intensity during base training - avoid injury through prudence",
      "Use hills and varied terrain for strength work instead of rigid gym routines",
      "Train through feel and response, not just pace and heart rate numbers"
    ],

    decision_framework: {
      when_to_use: [
        "Athlete responds better to flexible training than rigid plans",
        "Marathon-specific preparation (especially suits marathoners)",
        "Athlete has good self-awareness and body listening skills",
        "Training environment has varied terrain available",
        "Athlete prefers high-frequency running (6-7 days/week)"
      ],
      avoid_if: [
        "Athlete needs strict structure and accountability",
        "Training for shorter distances like 5K (less emphasis on medium-long runs)",
        "Athlete struggles with consistency or self-discipline",
        "Limited time available (needs lower frequency approach)"
      ],
      ideal_for: [
        "Marathon and half-marathon training",
        "Experienced runners who understand their bodies",
        "Athletes transitioning from injury who need adaptive approach",
        "Runners training in varied terrain and weather conditions"
      ]
    },

    workout_structure_preference: WorkoutStructure.PROGRESSIVE_INTERVALS,

    workout_design_rules: [
      "Medium-long runs are scheduled 2-3x per week at 75-85% of long run distance",
      "Tempo runs adapt to situation: flat, hilly, trail, road - adjust pace accordingly",
      "Long runs can include progressive pace, surges, or marathon-pace segments",
      "VO2max intervals are flexible: 3-5 min repeats, distance not rigidly prescribed",
      "Hill circuits replace traditional track intervals - more functional strength",
      "Every workout can be adjusted based on athlete feedback from previous day",
      "Warm-up and cool-down are essential but flexible in duration"
    ],

    notable_achievements: [
      "Coached Dathan Ritzenhein to 2:07 marathon",
      "Coached multiple Olympic Marathon Trials qualifiers",
      "Worked with Becky Wade, Jorge Torres, Sara Slattery",
      "Known for individualized, adaptive coaching approach"
    ],

    signature_workouts: [
      {
        name: "Medium-Long Run",
        description: "12-16 mile run at comfortable aerobic pace. Core Hudson workout - builds aerobic strength without excessive fatigue."
      },
      {
        name: "Situational Tempo",
        description: "Threshold effort adapted to terrain and conditions. On hills, slower pace but same effort. Flexible duration 20-40 min."
      },
      {
        name: "Long Run with Surges",
        description: "Long run with 2-5 minute surges at marathon pace or faster. Simulates race fatigue and pace changes."
      },
      {
        name: "Hill Circuits",
        description: "Continuous running on hilly course with hard uphill efforts and controlled downhills. Builds strength and economy."
      }
    ]
  },

  // Jack Daniels and Hansons profiles simplified for now - full LLM-friendly versions pending
  {
    id: "jack_daniels",
    name: "Jack Daniels",
    primary_style: CoachingStyle.LACTATE_THRESHOLD,
    sport_focus: ["running", "middle_distance", "distance"],

    philosophy_summary: "Scientific, VDOT-based training. Every pace has a specific physiological purpose. Quality over quantity.",

    core_beliefs: [
      "Every training intensity targets a specific physiological system",
      "VDOT determines all training paces based on current fitness",
      "Training stress limited: no more than 10% quality per week",
      "Long runs capped at 25% weekly mileage or 150 minutes"
    ],

    training_phases: [
      {
        name: "Foundation",
        tag: "foundation",
        duration_weeks: "6+",
        primary_goals: ["Build aerobic base", "Injury prevention"],
        intensity_distribution: { easy: "100% Easy pace", moderate: "0%", hard: "0%", recovery_week_adjustment: "N/A" },
        weekly_structure: "Easy running only with strides",
        key_workouts: [
          { name: "Easy Runs", purpose: "Aerobic development", frequency: "5-6x per week" },
          { name: "Long Runs", purpose: "Endurance building", frequency: "1x per week" }
        ],
        progression_strategy: "Build volume gradually"
      }
    ],

    key_principles: [
      "Easy (E): 59-74% VO2max for recovery and aerobic development",
      "Marathon (M): 80-90% VO2max for race-specific endurance",
      "Threshold (T): 83-88% VO2max for lactate clearance",
      "Interval (I): 95-100% VO2max for VO2max development",
      "Repetition (R): 105-120% VO2max for speed and economy"
    ],

    decision_framework: {
      when_to_use: ["Athlete wants scientific, data-driven training", "Clear race goals with specific paces"],
      avoid_if: ["Athlete prefers feel-based training"],
      ideal_for: ["All distances", "Data-oriented athletes"]
    },

    workout_structure_preference: WorkoutStructure.PYRAMID,
    workout_design_rules: ["Every workout has specific physiological purpose", "Use VDOT tables for all paces"],

    notable_achievements: ["Daniels' Running Formula", "Coached Olympic athletes and NCAA champions"]
  },

  {
    id: "hansons",
    name: "Hanson's Method",
    primary_style: CoachingStyle.CUMULATIVE_FATIGUE,
    sport_focus: ["marathon"],

    philosophy_summary: "Train tired to race fresh. Cumulative fatigue from high-frequency training simulates marathon conditions. Cap long runs at 16 miles, use 3 SOS workouts per week.",

    core_beliefs: [
      "Cumulative fatigue from weekly training simulates marathon better than single long runs",
      "Cap long runs at 16 miles to avoid excessive single-session damage",
      "Three SOS (Something of Substance) workouts per week develop all systems",
      "Train tired to race fresh - embrace fatigue during training",
      "6 days per week minimum for cumulative effect"
    ],

    training_phases: [
      {
        name: "Base Building",
        tag: "base",
        duration_weeks: "10",
        primary_goals: ["Build aerobic foundation", "Accumulate volume", "Establish 6-day frequency"],
        intensity_distribution: { easy: "90% easy running", moderate: "10% moderate", hard: "0%", recovery_week_adjustment: "Reduce volume by 25%" },
        weekly_structure: "6 days running. Progressive long runs. Easy runs fill remaining days.",
        key_workouts: [
          { name: "Easy Runs", purpose: "Volume accumulation and recovery", frequency: "6x per week" },
          { name: "Progressive Long Run", purpose: "Build endurance gradually", frequency: "1x per week" }
        ],
        progression_strategy: "Increase volume steadily. Build to 6-day consistency."
      },
      {
        name: "Strength Phase",
        tag: "strength",
        duration_weeks: "6",
        primary_goals: ["Build lactate threshold", "Introduce quality work", "Maintain high frequency"],
        intensity_distribution: { easy: "75% easy", moderate: "20% threshold", hard: "5% speed", recovery_week_adjustment: "Reduce volume, keep intensity" },
        weekly_structure: "6 days running. 3 SOS workouts: tempo, speed, long run. Easy days between.",
        key_workouts: [
          { name: "Tempo Run", purpose: "Build lactate threshold", frequency: "1x per week" },
          { name: "Speed Workout", purpose: "Develop leg turnover", frequency: "1x per week" },
          { name: "Long Run (16 miles max)", purpose: "Build endurance without excess fatigue", frequency: "1x per week" }
        ],
        progression_strategy: "Increase SOS workout difficulty. Maintain cumulative fatigue."
      },
      {
        name: "Peak Phase",
        tag: "peak",
        duration_weeks: "3",
        primary_goals: ["Marathon-pace work under fatigue", "Simulate race conditions", "Peak cumulative adaptation"],
        intensity_distribution: { easy: "70% easy", moderate: "25% marathon pace", hard: "5% speed", recovery_week_adjustment: "N/A - short phase" },
        weekly_structure: "6 days running. Marathon-pace long runs and tempo runs. Speed work. Cumulative fatigue intentional.",
        key_workouts: [
          { name: "16-Mile Long Run", purpose: "Practice marathon effort under fatigue", frequency: "1x per week" },
          { name: "10-Mile Marathon-Pace Run", purpose: "Build race-specific endurance", frequency: "1x per week" },
          { name: "Speed/Tempo", purpose: "Maintain sharpness", frequency: "1x per week" }
        ],
        progression_strategy: "Peak cumulative fatigue. Train tired consistently."
      }
    ],

    key_principles: [
      "Long runs capped at 16 miles - weekly fatigue provides marathon adaptation",
      "Three SOS workouts per week minimum (tempo, speed, long run)",
      "Train tired deliberately - cumulative fatigue is the method",
      "6 days running per week minimum to achieve cumulative effect",
      "Moderate volume (55-70 miles/week) with high frequency beats high volume low frequency",
      "10-day taper only (much shorter than traditional)",
      "Every run has purpose - no junk miles"
    ],

    decision_framework: {
      when_to_use: ["Marathon training", "Athlete can handle high frequency", "Moderate weekly volume preferred over extreme long runs"],
      avoid_if: ["Half marathon or shorter", "Cannot train 6 days per week", "Prefers lower frequency high volume"],
      ideal_for: ["Marathon-specific training", "Runners who respond well to consistent stimulus"]
    },

    workout_structure_preference: WorkoutStructure.MICROCYCLE,
    workout_design_rules: [
      "Cap long runs at 16 miles maximum",
      "Schedule 3 SOS workouts per week (never more, rarely less)",
      "Easy days must be truly easy to allow cumulative fatigue training",
      "Embrace training while tired - this is the methodology"
    ],

    notable_achievements: ["Coached Desiree Linden (Boston Marathon champion)", "Brian Sell (Olympic Trials winner)", "Hansons-Brooks Distance Project"]
  }
];

/**
 * Get all coach profiles
 */
export function getAllCoaches(): CoachProfile[] {
  return COACHES;
}

/**
 * Get specific coach profile by ID
 */
export function getCoachById(coachId: string): CoachProfile | undefined {
  return COACHES.find(coach => coach.id === coachId);
}

/**
 * Generate coaching instructions based on RuntimeContext
 *
 * Checks RuntimeContext for 'coachingMethod' key and returns
 * coach-specific instructions to guide agent behavior.
 */
export function generateCoachingInstructions(runtimeContext?: RuntimeContext): string {
  if (!runtimeContext) {
    return getDefaultCoachingInstructions();
  }

  const coachId = runtimeContext.get('coachId') as string | undefined;

  if (!coachId) {
    return getDefaultCoachingInstructions();
  }

  const coach = getCoachById(coachId);

  if (!coach) {
    return getDefaultCoachingInstructions();
  }

  return formatCoachInstructions(coach);
}

/**
 * Default coaching instructions when no specific coach is selected
 */
function getDefaultCoachingInstructions(): string {
  return `
You are a world-class endurance training periodization expert. You design multi-week training phases that follow proven periodization principles.

## Core Periodization Principles

**1. Training Phases:**
- Base Building: Aerobic foundation, high volume, low intensity (4-12 weeks)
- Build/Specific Preparation: Race-specific work, threshold, VO2max (4-8 weeks)
- Peak/Sharpening: Race pace, high intensity, reduced volume (2-4 weeks)
- Taper: Maintain intensity, reduce volume for recovery (1-3 weeks)
- Recovery/Transition: Active recovery between cycles (1-2 weeks)

**2. Progressive Overload:**
- Gradual TSS increase (maximum of 10% per week)
- 3:1 or 2:1 loading patterns (3 build weeks, 1 recovery week)
- Respect athlete's current fitness baseline
- Consider cumulative fatigue

**3. Race Priority System:**
- A-Priority: Peak race, full taper (target race)
- B-Priority: Important race, mini-taper (tune-up race)
- C-Priority: Training race, no taper (fitness check)

**4. Critical Workouts:**
- Each week should have 2-3 key sessions that define the training stimulus
- Examples: long run, tempo run, short / long intervals, race-pace, over-under, hill work, pyramids
- Recovery runs fill in between quality sessions

## Phase Planning Process

When designing phases:

1. **Assess timeline:**
   - Count weeks from current date to A-priority race
   - Work backward from race date
   - Account for B and C priority races

2. **Allocate phases:**
   - Taper: Last 1-3 weeks before A-race
   - Peak: 2-4 weeks before taper
   - Build: 4-8 weeks before peak
   - Base: Remaining weeks (if >12 weeks total)

3. **Structure each phase:**
   - Define weekly focus and progression
   - Identify critical workouts per week
   - Plan recovery weeks (every 3-4 weeks)
   - Integrate B/C races as appropriate

4. **Weekly structure:**
   - Each week needs clear training objectives
   - Critical workouts drive adaptation
   - Adequate recovery between hard sessions

## Output Requirements

Generate a structured training plan with:
- Phase name and training tag/focus
- Phase description and objectives
- Week-by-week breakdown with:
  - Week identifier (e.g., "week-1", "week-2")
  - Start and end dates
  - Weekly focus/description
  - Critical workouts (2-3 per week) with brief descriptions
`;
}

/**
 * Format coach profile into LLM-friendly agent instructions
 */
function formatCoachInstructions(coach: CoachProfile): string {
  // Format core beliefs
  const coreBeliefsList = coach.core_beliefs
    .map(belief => `- ${belief}`)
    .join('\n');

  // Format training phases with detailed structure
  const phaseDetails = coach.training_phases
    .map(phase => {
      const goals = phase.primary_goals.map(g => `  - ${g}`).join('\n');
      const workouts = phase.key_workouts.map(w => `  - **${w.name}** (${w.frequency}): ${w.purpose}`).join('\n');

      return `
**${phase.name} (${phase.tag})** - ${phase.duration_weeks} weeks
Goals:
${goals}

Weekly Structure: ${phase.weekly_structure}

Key Workouts:
${workouts}

Intensity Distribution:
  - Easy: ${phase.intensity_distribution.easy}
  - Moderate: ${phase.intensity_distribution.moderate}
  - Hard: ${phase.intensity_distribution.hard}
  - Recovery Weeks: ${phase.intensity_distribution.recovery_week_adjustment}

Progression: ${phase.progression_strategy}
`;
    }).join('\n---\n');

  // Format key principles
  const principlesList = coach.key_principles
    .map(principle => `- ${principle}`)
    .join('\n');

  // Format workout design rules
  const workoutRules = coach.workout_design_rules
    .map(rule => `- ${rule}`)
    .join('\n');

  // Format decision framework
  const whenToUse = coach.decision_framework.when_to_use.map(w => `  - ${w}`).join('\n');
  const avoidIf = coach.decision_framework.avoid_if.map(a => `  - ${a}`).join('\n');
  const idealFor = coach.decision_framework.ideal_for.map(i => `  - ${i}`).join('\n');

  return `
## Coaching Methodology: ${coach.name}

### Philosophy
${coach.philosophy_summary}

### Core Beliefs
${coreBeliefsList}

---

### Training Phases
${phaseDetails}

---

### Key Coaching Principles
${principlesList}

---

### Workout Design Rules
${workoutRules}

---

### When to Apply This Methodology

**Use ${coach.name}'s approach when:**
${whenToUse}

**Avoid if:**
${avoidIf}

**Ideal for:**
${idealFor}

---

### Instructions for You

You are now coaching in the style of **${coach.name}** (${coach.primary_style} approach).

When generating training plans:
1. Follow the phase structure and progression strategies above
2. Apply the intensity distributions for the current training phase
3. Use the characteristic workouts and weekly structures
4. Adhere strictly to the workout design rules
5. Embody the core beliefs in all recommendations

When designing workouts:
- Reference the key workouts for each phase
- Maintain the specified intensity distributions
- Follow the workout structure preference: ${coach.workout_structure_preference}
- Apply the coaching principles consistently

**Remember:** Every recommendation should reflect ${coach.name}'s methodology. Your coaching style, workout structure, and training philosophy must align with this approach.
`;
}

/**
 * Format phase summary for getCoachSummary
 */
function getPhasesSummaryText(coach: CoachProfile): string {
  return coach.training_phases
    .map(phase => `${phase.name} (${phase.tag})`)
    .join(' → ');
}

/**
 * Get available coach IDs for selection
 */
export function getCoachIds(): string[] {
  return COACHES.map(coach => coach.id);
}

/**
 * Get coach summary for selection UI
 */
export function getCoachSummary(coachId: string): string | undefined {
  const coach = getCoachById(coachId);
  if (!coach) return undefined;

  const phasesSummary = getPhasesSummaryText(coach);
  return `${coach.name} - ${coach.primary_style} approach. ${coach.philosophy_summary} Phases: ${phasesSummary}`;
}

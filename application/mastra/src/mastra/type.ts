
import z from "zod";

// Define types for better type safety
type WorkoutSegment = {
  type: "segment";
  duration: number;
  intensity_metric: "pace" | "power" | "heart_rate";
  target_range: { min: number; max: number };
  description: string;
  pre: number;
};

type LoopStart = {
  type: "loop_start";
  id: string;
  repeat: number;
};

type LoopEnd = {
  type: "loop_end";
  id: string;
};

type WorkoutItem = WorkoutSegment | LoopStart | LoopEnd;

const WorkoutSegmentSchema = z.object({
  type: z.literal("segment").describe("Indicates this is a workout segment"),
  distance_range: z.object({
    min: z.number().min(0).describe("Minimum distance in kilometers"),
    max: z.number().min(0).describe("Maximum distance in kilometers"),
  }).optional().describe("Optional range of distance for the segment in kilometers"),
  duration: z.number().min(0.1).describe("Duration of the segment in minutes"),
  intensity_metric: z.enum(["pace", "power", "heart_rate"]).describe("Metric for intensity: pace (min/km), power (watts), or heart_rate (bpm)"),
  target_range: z.object({
    min: z.number().describe("Minimum target value for the intensity metric, if pace then in integer (seconds/km), if power then in watts, if heart_rate then in bpm"),
    max: z.number().describe("Maximum target value for the intensity metric, if pace then in integer (seconds/km), if power then in watts, if heart_rate then in bpm"),
  }).describe("Range of target values for the intensity metric"),
  description: z.string().describe("Human-readable description of the segment"),
  tags: z.array(z.string()).optional().describe("Optional array of tags for categorization"),
  pre: z.number().min(0).max(10).describe("Pre score from 0-10 indicating difficulty/preparation level")
}) satisfies z.ZodType<WorkoutSegment>;

const LoopStartSchema = z.object({
  type: z.literal("loop_start").describe("Marks the start of a repeating loop"),
  id: z.string().describe("Unique identifier for the loop"),
  repeat: z.number().min(1).describe("Number of times the loop should repeat"),
}) satisfies z.ZodType<LoopStart>;

const LoopEndSchema = z.object({
  type: z.literal("loop_end").describe("Marks the end of a repeating loop"),
  id: z.string().describe("Unique identifier matching the corresponding loop_start"),
}) satisfies z.ZodType<LoopEnd>;

// Use z.lazy for recursive schema to allow nested loops - wait, no longer needed since flat
const WorkoutItemSchema = z.union([WorkoutSegmentSchema, LoopStartSchema, LoopEndSchema]);

export const WorkoutPlanSchema = z.object({
  title: z.string().describe("Title of the workout plan"),
  id: z.string().describe("Unique identifier for the workout plan"),
  week_id: z.string().optional().describe("Identifier of the parent week this workout belongs to"),
  date: z.coerce.date().optional().describe("Date the workout assigned"),
  description: z.string().describe("Detailed description of the workout plan or error message if workout cannot be generated"),
  detail: z.array(WorkoutItemSchema).describe("Array of workout items including segments and loop markers (empty array if error)"),
  estimated_tss: z.number().nullable().optional().describe("Estimated Training Stress Score for the workout (null if unavailable)"),
  total_time: z.number().nullable().optional().describe("Total estimated time for the workout in minutes (null if unavailable)"),
  total_distance: z.number().nullable().optional().describe("Total estimated distance for the workout in kilometers (null if unavailable)"),
});
export type WorkoutPlan = z.infer<typeof WorkoutPlanSchema>;

// Phase Planning Schemas
export const RaceEventSchema = z.object({
  date: z.coerce.date().describe("Race date"),
  priority: z.enum(["A", "B", "C"]).describe("Race priority: A=peak race, B=tune-up, C=training race"),
  distance: z.number().describe("Race distance in kilometers"),
  name: z.string().optional().describe("Race name or description"),
});

export const CriticalWorkoutSchema = z.object({
  id: z.string().describe("Unique identifier for the critical workout"),
  description: z.string().describe("Brief description of the critical workout type and purpose"),
});

export const TrainingWeekSchema = z.object({
  week_id: z.string().describe("Week identifier (e.g., 'week-1', 'base-week-3')"),
  phase_id: z.string().describe("Identifier of the parent training phase"),
  start_date: z.coerce.date().describe("Week start date (typically Monday)"),
  end_date: z.coerce.date().describe("Week end date (typically Sunday)"),
  description: z.string().describe("Weekly focus and training objectives"),
  weekly_mileage: z.number().nullable().optional().describe("Planned total weekly mileage in kilometers"),
  critical_workouts: z.array(CriticalWorkoutSchema).describe("Key workouts for this week (typically 2-3)"),
});

export const TrainingPhaseSchema = z.object({
  phase_id: z.string().describe("Unique identifier for the training phase"),
  name: z.string().describe("Phase name (e.g., 'Base Building', 'Specific Preparation')"),
  tag: z.string().describe("Short tag/label for the phase (e.g., 'base', 'build', 'peak', 'taper')"),
  description: z.string().describe("Phase objectives and training focus"),
  weeks: z.array(TrainingWeekSchema).describe("Week-by-week breakdown for this phase"),
  workout_focus: z.array(z.string()).min(1).describe("Primary training focus areas for the phase (e.g., ['aerobic base'], ['threshold', 'VO2max'], ['race pace', 'speed endurance'])"),
});

export type RaceEvent = z.infer<typeof RaceEventSchema>;
export type CriticalWorkout = z.infer<typeof CriticalWorkoutSchema>;
export type TrainingWeek = z.infer<typeof TrainingWeekSchema>;
export type TrainingPhase = z.infer<typeof TrainingPhaseSchema>;

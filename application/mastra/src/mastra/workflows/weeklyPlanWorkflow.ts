import { createStep, createWorkflow } from '@mastra/core/workflows';
import { z } from 'zod';
import { WorkoutPlanSchema, RaceEventSchema } from '../type';

// Input schema for single day workout request
const DailyWorkoutRequestSchema = z.object({
  id: z.string().describe("Unique identifier for this workout day"),
  date: z.coerce.date().describe("Date for the workout (accepts Date object or ISO string)"),
  workout_type: z.string().describe("Type of workout (e.g., easy run, intervals, tempo)"),
  previous_workout: z.string().optional().describe("Description of previous workout for context"),
  workout_target: z.string().describe("Goal or target for this workout"),
  distance_range: z.object({
    min: z.number(),
    max: z.number(),
  }).optional().describe("Target distance range in km"),
  time_range: z.object({
    min: z.number(),
    max: z.number(),
  }).optional().describe("Target time range in minutes"),
  zone_distribution: z.string().optional().describe("Desired intensity zone distribution"),
  target_zone: z.string().optional().describe("Primary target zone"),
});

// Step to process single workout using workout-expert agent
const processDailyWorkout = createStep({
  id: 'process-daily-workout',
  description: 'Generate workout plan for a single day using workout-expert agent',
  inputSchema: DailyWorkoutRequestSchema,
  outputSchema: z.object({
    id: z.string(),
    workoutPlan: WorkoutPlanSchema,
  }),
  execute: async ({ inputData, mastra, runtimeContext, writer }) => {
    const {
      id,
      date,
      workout_type,
      previous_workout,
      workout_target,
      distance_range,
      time_range,
      zone_distribution,
      target_zone
    } = inputData;

    // Build prompt for workout-expert
    let prompt = `Generate a ${workout_type} workout plan with the following requirements:
- Date: ${date.toISOString()}
- Target: ${workout_target}`;

    if (previous_workout) {
      prompt += `\n- Previous workout: ${previous_workout}`;
    }
    if (distance_range) {
      prompt += `\n- Distance range: ${distance_range.min}-${distance_range.max} km`;
    }
    if (time_range) {
      prompt += `\n- Time range: ${time_range.min}-${time_range.max} minutes`;
    }
    if (zone_distribution) {
      prompt += `\n- Zone distribution: ${zone_distribution}`;
    }
    if (target_zone) {
      prompt += `\n- Target zone: ${target_zone}`;
    }

    // Get workout expert agent
    const agent = mastra?.getAgent('workoutExpert');
    if (!agent) {
      throw new Error('workoutExpert agent not found');
    }

    // Generate workout plan with structured output
    const stream = await agent.stream(
      [{ role: 'user', content: prompt }],
      {
        structuredOutput: {schema: WorkoutPlanSchema},
        runtimeContext: runtimeContext
      }
    );
    await stream.objectStream.pipeTo(writer!)
    const object = await stream!.object
    // Add id and date to the plan
    const workoutPlan = {
      ...object,
      id,
      date,
    };
    return {
      id,
      workoutPlan,
    };
  },
});

// Step to aggregate results into dict
const aggregateWorkouts = createStep({
  id: 'aggregate-workouts',
  description: 'Aggregate all workout plans into a dictionary keyed by id',
  inputSchema: z.array(z.object({
    id: z.string(),
    workoutPlan: WorkoutPlanSchema,
  })),
  outputSchema: z.record(z.string(), WorkoutPlanSchema),
  execute: async ({ inputData }) => {
    const result: Record<string, any> = {};
    for (const item of inputData) {
      result[item.id] = item.workoutPlan;
    }
    return result;
  },
});

// Main workflow
export const generateDetailedWorkoutsWorkflow = createWorkflow({
  id: 'generate-detailed-workouts',
  description: 'Generate 1-7 detailed workout prescriptions with parallel processing (max 3 concurrent). Converts high-level workout descriptions into complete structured plans with: warmup/cooldown segments, specific intervals with pacing zones, heart rate targets, duration and distance for each segment, and execution instructions. Efficiently processes multiple workouts from different weeks in a single call.',
  inputSchema: z.object({
    description: z.string().describe("Overall description or goal for this set of workouts"),
    available_days_per_week: z.number().min(3).max(7).describe("Number of days per week available for training (3-7)"),
    workouts: z.array(DailyWorkoutRequestSchema).min(1).max(7).describe("Array of daily workout specifications to generate"),
  }),
  outputSchema: z.record(z.string(), WorkoutPlanSchema),
})
  .map(async ({ inputData }) => inputData.workouts)
  .foreach(processDailyWorkout, { concurrency: 3 })
  .then(aggregateWorkouts)
  .commit();

// Export with both names for backward compatibility
export const weeklyPlanWorkflow = generateDetailedWorkoutsWorkflow;

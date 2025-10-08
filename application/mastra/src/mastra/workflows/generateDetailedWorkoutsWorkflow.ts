import { createStep, createWorkflow } from '@mastra/core/workflows';
import { z } from 'zod';
import { WorkoutPlanLLMSchema, WorkoutPlanOutputSchema, TrainingWeekSchema } from '../type';
import logger from '../../logger';

// Input schema for single day workout request
const DailyWorkoutRequestSchema = z.object({
  id: z.string().describe("Unique identifier for this workout day"),
  date: z.coerce.date().describe("Date for the workout (accepts Date object or ISO string)"),
  workout_type: z.string().describe("Type of workout (e.g., easy run, intervals, tempo)"),
  workout_target: z.string().describe("Goal or target for this workout"),
  distance_range: z.object({
    min: z.number(),
    max: z.number(),
  }).nullable().optional().describe("Target distance range in km"),
  time_range: z.object({
    min: z.number(),
    max: z.number(),
  }).nullable().optional().describe("Target time range in minutes"),
  zone_distribution: z.string().nullable().optional().describe("Desired intensity zone distribution"),
  target_zone: z.string().nullable().optional().describe("Primary target zone"),
});


// Step 1: Enhance TrainingWeek to complete weekly workout plan
const enhanceWeeklyWorkouts = createStep({
  id: 'enhance-weekly-workouts',
  description: 'Use workout-enhancer agent to convert critical_workouts and fill complete week with proper workout distribution',
  inputSchema: z.object({
    training_week: TrainingWeekSchema,
    available_days_per_week: z.number().min(3).max(7),
    phase_id: z.string().optional().describe("Parent phase identifier"),
  }),
  outputSchema: z.array(DailyWorkoutRequestSchema.extend({
    phase_id: z.string(),
    week_id: z.string(),
  })),
  execute: async ({ inputData, mastra, runtimeContext }) => {
    const { training_week, available_days_per_week, phase_id } = inputData;

    // Get workout enhancer agent
    const agent = mastra?.getAgent('workoutEnhancer');
    if (!agent) {
      throw new Error('workoutEnhancer agent not found');
    }

    // Build comprehensive prompt for workout enhancer
    const criticalWorkoutsDesc = training_week.critical_workouts
      .map(w => `- ${w.id}: ${w.description}`)
      .join('\n');

    // Convert dates to Date objects if they're strings
    const startDate = training_week.start_date instanceof Date
      ? training_week.start_date
      : new Date(training_week.start_date);
    const endDate = training_week.end_date instanceof Date
      ? training_week.end_date
      : new Date(training_week.end_date);

    const prompt = `Generate a COMPLETE weekly workout plan from this training week structure.

**Week Context:**
- Week ID: ${training_week.week_id}
- Week dates: ${startDate.toISOString().split('T')[0]} to ${endDate.toISOString().split('T')[0]}
- Weekly focus: ${training_week.description}
- Target weekly mileage: ${training_week.weekly_mileage || 'Not specified'} km
- Available training days: ${available_days_per_week} days/week

**Critical Workouts to Include (${training_week.critical_workouts.length}):**
${criticalWorkoutsDesc}

**Your Task:**
1. Convert each critical workout into a DailyWorkoutRequest with appropriate date assignment
2. Distribute critical workouts intelligently across the week (e.g., Tue/Thu/Sat pattern)
3. Fill remaining days with easy runs, recovery runs, or rest days based on training principles
4. Ensure proper hard/easy sequencing and weekly volume distribution

Return a COMPLETE array of ${available_days_per_week} DailyWorkoutRequest objects.

Each workout must have:
- id: unique identifier
- date: ISO date string within the week range
- workout_type: specific type (e.g., "tempo run", "intervals", "long run", "easy run", "recovery run", "rest day")
- workout_target: clear goal description
- distance_range (optional): {min, max} in km - OMIT this field entirely for rest days, do not use null
- time_range (optional): {min, max} in minutes - OMIT this field entirely for rest days, do not use null
- zone_distribution (optional): e.g., "Zone 2: 100%" - OMIT this field entirely for rest days, do not use null
- target_zone (optional): e.g., "Zone 2" - OMIT this field entirely for rest days, do not use null

IMPORTANT: For rest days, only include id, date, workout_type, and workout_target. Do NOT include distance_range, time_range, zone_distribution, or target_zone fields at all.`;

    const stream = await agent.stream(
      [{ role: 'user', content: prompt }],
      {
        structuredOutput: { schema: z.array(DailyWorkoutRequestSchema) },
        runtimeContext: runtimeContext
      }
    );

    // Consume the stream to get final result
    const finalResult = await stream.object
    if (!finalResult || !Array.isArray(finalResult)) {
      console.error('❌ workoutEnhancer failed to generate structured output');
      throw new Error('Failed to generate daily workouts: Invalid structured output from workoutEnhancer');
    }

    console.log(`✅ Generated ${finalResult.length} daily workouts for ${training_week.week_id}`);
    // Attach phase_id and week_id to each workout
    return finalResult.map(workout => ({
      ...workout,
      phase_id: phase_id || training_week.phase_id,
      week_id: training_week.week_id,
    }));
  },
});

// Step 2: Process each workout using workout-expert agent and store to API
const processDailyWorkout = createStep({
  id: 'process-daily-workout',
  description: 'Generate detailed workout plan using workout-expert agent with structured segments, then store to api-service',
  inputSchema: DailyWorkoutRequestSchema.extend({
    phase_id: z.string().describe("Parent phase identifier"),
    week_id: z.string().describe("Parent week identifier"),
  }),
  outputSchema: z.object({
    id: z.string(),
    workoutPlan: WorkoutPlanOutputSchema,
  }),
  execute: async ({ inputData, mastra, runtimeContext }) => {
    const {
      id,
      date,
      workout_type,
      workout_target,
      distance_range,
      time_range,
      zone_distribution,
      target_zone,
      phase_id,
      week_id
    } = inputData;

    // Build concise prompt - agent already has coach methodology and design principles
    const specs = [
      `Type: ${workout_type}`,
      `Date: ${date.toISOString().split('T')[0]}`,
      `Goal: ${workout_target}`,
      distance_range && `Distance: ${distance_range.min}-${distance_range.max} km`,
      time_range && `Duration: ${time_range.min}-${time_range.max} minutes`,
      zone_distribution && `Zones: ${zone_distribution}`,
      target_zone && `Target: ${target_zone}`
    ].filter(Boolean).join('\n');

    const prompt = `Generate a detailed workout plan with structured segments:

${specs}
Provide the output in the specified structured format.`;

    // Get workout expert agent
    const agent = mastra?.getAgent('workoutExpert');
    if (!agent) {
      throw new Error('workoutExpert agent not found');
    }
    logger.info(`Generating detailed workout for ${id} (${workout_type}) on ${date.toISOString().split('T')[0]}, specs:\n${specs}`);

    // Generate workout plan with structured output (LLM schema - no week_id/workout_id/date)
    // Retry mechanism with exponential backoff
    const maxRetries = 3;
    let finalResult = null;
    let lastError = null;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        logger.info(`Attempt ${attempt}/${maxRetries} to generate workout ${id}`);

        const result = await agent.generate(
          [{ role: 'user', content: prompt }],
          {
            structuredOutput: { schema: WorkoutPlanLLMSchema },
            runtimeContext: runtimeContext
          }
        );

        finalResult = result.object;

        if (finalResult) {
          logger.info(`✅ Successfully generated workout ${id} on attempt ${attempt}`);
          break;
        } else {
          logger.warn(`Attempt ${attempt} failed: No structured output. Response: ${result.text?.substring(0, 200)}...`);
          lastError = new Error(`No structured output from workoutExpert (attempt ${attempt})`);
        }
      } catch (error) {
        logger.error(`Attempt ${attempt} failed with error:`, error);
        lastError = error;
      }

      // Wait before retry (exponential backoff: 1s, 2s, 4s)
      if (attempt < maxRetries) {
        const waitMs = Math.pow(2, attempt - 1) * 1000;
        logger.info(`Waiting ${waitMs}ms before retry...`);
        await new Promise(resolve => setTimeout(resolve, waitMs));
      }
    }

    if (!finalResult) {
      console.error(`❌ workoutExpert failed to generate structured output for workout ${id} after ${maxRetries} attempts`);
      throw new Error(`Failed to generate detailed workout plan for ${id} after ${maxRetries} retries: ${lastError?.message || 'Invalid structured output'}`);
    }

    // Build workout plan output with metadata
    const workoutPlanOutput: any = {
      ...finalResult,
      workout_id: id,
      week_id,
      date,
      phase_id,
      stored: false,
    };

    // Store to API service
    const accessToken = runtimeContext?.get('accessToken');
    const apiBaseUrl = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8002';

    try {
      if (!accessToken) {
        logger.warn('No access token found in runtime context, skipping API storage');
      } else {
        logger.info(`Storing workout to API: ${apiBaseUrl}/training-plans/workouts`);
        // Map workout plan to API request format
        const dayOfWeek = new Date(date).getDay(); // 0=Sunday, need to convert to 0=Monday
        const adjustedDayOfWeek = dayOfWeek === 0 ? 6 : dayOfWeek - 1;

        const apiRequest = {
          // user_id omitted - API will use authenticated user
          phase_id,
          week_id,
          name: finalResult.title,
          day_of_week: adjustedDayOfWeek,
          workout_type,
          segments: finalResult.detail, // API expects array, not JSON string
          workout_metadata: {
            estimated_tss: finalResult.estimated_tss,
            total_time: finalResult.total_time,
            total_distance: finalResult.total_distance,
            description: finalResult.description,
          },
        };

        const response = await fetch(`${apiBaseUrl}/training-plans/workouts`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(apiRequest),
        });

        if (response.ok) {
          workoutPlanOutput.stored = true;
          logger.info(`✅ Stored workout ${id} to database`);
        } else {
          const errorText = await response.text();
          logger.error(`❌ Failed to store workout ${id}: ${response.status} - ${errorText}`);
          logger.error(`Request payload:`, JSON.stringify(apiRequest, null, 2));
        }
      }
    } catch (error) {
      logger.error(`❌ Error storing workout ${id} to API:`, error);
      logger.error(`API URL: ${apiBaseUrl}`);
      logger.error(`Has access token: ${!!accessToken}`);
    }

    console.log(`✅ Generated detailed workout plan for ${id} (${workout_type})`);
    return {
      id,
      workoutPlan: workoutPlanOutput,
    };
  },
});

// Step 3: Aggregate results into dictionary
const aggregateWorkouts = createStep({
  id: 'aggregate-workouts',
  description: 'Aggregate all workout plans into a dictionary keyed by workout id',
  inputSchema: z.array(z.object({
    id: z.string(),
    workoutPlan: WorkoutPlanOutputSchema,
  })),
  outputSchema: z.record(z.string(), WorkoutPlanOutputSchema),
  execute: async ({ inputData }) => {
    const result: Record<string, any> = {};
    for (const item of inputData) {
      result[item.id] = item.workoutPlan;
    }
    return result;
  },
});

// Main workflow: TrainingWeek → Full Weekly Workout Plans
export const generateDetailedWorkoutsWorkflow = createWorkflow({
  id: 'generate-detailed-workouts',
  description: 'Takes a TrainingWeek from runningPhaseWorkflow and generates complete detailed workout plans. Flow: (1) Use workout-enhancer to convert critical_workouts and fill complete week, (2) Use workout-expert to generate detailed workout plans with segments/intervals/pacing (parallel), (3) Store workouts to api-service database, (4) Return dictionary of complete WorkoutPlans keyed by id.',
  inputSchema: z.object({
    training_week: TrainingWeekSchema.describe("Training week from phase planner with critical workouts"),
    available_days_per_week: z.number().min(3).max(7).describe("Number of days per week available for training"),
    phase_id: z.string().optional().describe("Parent phase identifier"),
  }),
  outputSchema: z.record(z.string(), WorkoutPlanOutputSchema),
})
  // Step 1: workout-enhancer converts and fills complete week
  .then(enhanceWeeklyWorkouts)
  // Step 2: workout-expert generates detailed plans for each workout (parallel)
  .foreach(processDailyWorkout, { concurrency: 7 })
  // Step 3: Aggregate into dictionary
  .then(aggregateWorkouts)
  .commit();

// Export with both names for backward compatibility
export const weeklyPlanWorkflow = generateDetailedWorkoutsWorkflow;

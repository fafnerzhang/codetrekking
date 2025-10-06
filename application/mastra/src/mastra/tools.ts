import { createTool, InferUITool, InferUITools } from "@mastra/core/tools";
import { CoreMessage, Step, CoreToolMessage, VercelToolV5 } from "@mastra/core";
import { MastraUIMessage } from '@mastra/react'
import z from "zod";
import { logger } from "../logger";
import { UIMessage} from 'ai'
import { MastraMessageV2, AiMessageType } from "@mastra/core";
import { ChunkType } from "@mastra/core";
import { WorkoutPlanSchema, RaceEventSchema, TrainingPhaseSchema } from './type'
import { UIMessageWithMetadata } from "@mastra/core/agent";
import { STREAM_FORMAT_SYMBOL } from "@mastra/core/workflows/_constants";
import { StructuredOutputProcessor, type StructuredOutputOptions  } from "@mastra/core/processors"
import { google } from "@ai-sdk/google";
import { runningPhaseWorkflow } from './workflows/runningPhaseWorkflow';
import { generateDetailedWorkoutsWorkflow } from './workflows/weeklyPlanWorkflow';


export const workoutExpertTool = createTool({
    id: "workoutExpert",
    description: "A tool for generating single structured, data-driven running workout.",
    inputSchema: z.object({
        workoutRequirements: z.string().describe("User's workout requirements and goals")}),
    outputSchema: z.union([z.string(), WorkoutPlanSchema]),
    execute: async ({ mastra, context, runtimeContext, writer }) => {
    const message = context.workoutRequirements

    const agent = mastra?.getAgent("workoutExpert");
    console.log('🏁 Invoking workoutExpertTool with message:', message);
    // Write custom progress events (NOT raw agent chunks)

    const result = await agent?.generate(
        [{ role: 'user', content: message }],
        {
            structuredOutput: {
                schema: WorkoutPlanSchema
            },
            onFinish: (finalMessage) => {
                console.log(finalMessage.content)
                console.log('🏆 workoutExpertTool completed successfully:');
            },
            onError: (error) => {
                console.error('❌ Error in workoutExpertTool:', error);
                logger.error({ error }, 'Error in workoutExpertTool execution');
            }
        }
    )

    return result?.object
  },
});

// Workflow tool: Generate periodized training phases
export const generateTrainingPhases = createTool({
  id: "generateTrainingPhases",
  description: `Generate a complete periodized training plan with multiple phases (Base, Build, Peak, Taper).

  Use this tool when an athlete requests a training plan for an upcoming race. This tool will:
  - Create a structured periodization schedule based on race date and athlete profile
  - Generate week-by-week progression with specific training focus areas
  - Integrate recovery weeks and taper periods
  - Return high-level phase structure with critical workouts outlined

  After calling this tool, you should call generateDetailedWorkouts to create full workout details for the first 4 weeks.`,
  inputSchema: z.object({
    race_schedule: z.array(RaceEventSchema).min(1).describe("At least one race with A-priority required. Include race date, distance, priority (A/B/C), and optional name."),
    target_distance: z.number().describe("Primary target race distance in kilometers"),
    current_weekly_mileage: z.number().describe("Current weekly running volume in kilometers"),
    experience_level: z.enum(["beginner", "intermediate", "advanced"]).describe("Athlete's running experience level"),
    available_days_per_week: z.number().min(3).max(7).describe("Number of days per week available for training (3-7)"),
  }),
  outputSchema: z.object({
    phases: z.array(TrainingPhaseSchema),
  }),
  execute: async ({ context, mastra, runtimeContext }) => {
    console.log('🏃‍♂️ Executing generateTrainingPhases workflow...');

    const run = await mastra?.getWorkflow('runningPhaseWorkflow').createRunAsync();

    const result = await run?.startAsync({
      inputData: context,
      runtimeContext
    });

    console.log('✅ Training phases generated:', result?.result);
    return result?.result;
  }
});

// Workflow tool: Generate detailed workouts for weeks
export const generateDetailedWorkouts = createTool({
  id: "generateDetailedWorkouts",
  description: `Generate detailed, structured workout prescriptions for 1-7 days of training.

  Use this tool to convert high-level workout descriptions into complete workout plans with:
  - Specific segments (warmup, intervals, cooldown, etc.)
  - Precise pacing and heart rate zones
  - Duration and distance for each segment
  - Execution instructions and coaching cues

  IMPORTANT: This tool processes 1-7 workouts in parallel. When generating workouts for multiple weeks:
  - Combine ALL workouts from all weeks into a SINGLE array
  - Call this tool ONCE with the complete array (e.g., 12 workouts for 4 weeks)
  - Do NOT call this tool separately for each week

  Example: To generate weeks 1-4 with 3 workouts per week, pass an array of 12 workouts in one call.`,
  inputSchema: z.object({
    workouts: z.array(z.object({
      id: z.string(),
      date: z.string().or(z.date()),
      workout_type: z.string(),
      description: z.string(),
      duration_minutes: z.number().optional(),
      distance_km: z.number().optional(),
      intensity: z.string().optional(),
    })).min(1).max(7).describe("Array of 1-7 workout specifications to be detailed. Combine multiple weeks into one call.")
  }),
  outputSchema: z.object({
    detailed_workouts: z.array(WorkoutPlanSchema)
  }),
  execute: async ({ context, mastra, runtimeContext }) => {
    console.log(`🏋️ Executing generateDetailedWorkouts for ${context.workouts.length} workouts...`);

    const run = await mastra?.getWorkflow('generateDetailedWorkoutsWorkflow').createRunAsync();

    const result = await run?.startAsync({
      inputData: { workouts: context.workouts },
      runtimeContext
    });

    console.log('✅ Detailed workouts generated');
    return result?.result;
  }
});

const tools = {
  workoutExpertTool,
  generateTrainingPhases,
  generateDetailedWorkouts
};

export type WorkoutExpertTool = InferUITool<typeof workoutExpertTool>;
export type UITools = InferUITools<typeof tools>;
export type MyUIMessage = MastraUIMessage & { metadata?: Record<string, any> };
import { Agent } from "@mastra/core/agent";
import { currentModel } from "../model";
import { createMcpClientWithToken } from "../mcp/peakflow-client";
import { getApiBaseUrl } from "./utils";
import { WorkoutPlanSchema } from "../type";
import { formatIndicatorsForLLM } from "../utils/indicators";
import { generateCoachingInstructions } from "../utils/coaches";


export function createWorkoutExpert() {
  console.log("🏃‍♂️ Creating Dynamic Workout Expert...");

  // Cache for tools per access token to avoid recreating MCP client on every call
  const toolsCache = new Map<string, any>();

  return new Agent({
    id: "workoutExpert",
    name: "workoutExpert",
    description: "Creates structured, data-driven running workout plans based on athlete goals, fitness levels, and training preferences. Optimized for both single-day workouts and multi-day weekly plans.",
    instructions: ({runtimeContext}) => {
      const userIndicators = formatIndicatorsForLLM(runtimeContext);
      const coachMethodology = generateCoachingInstructions(runtimeContext);
      return `You are an expert running coach who GENERATES detailed, structured workout plans from high-level workout specifications.

## Coaching Methodology
${coachMethodology}

## Athlete Profile
${userIndicators}

## Your Role

You will receive workout specifications with parameters like:
- Workout type (easy run, intervals, tempo, recovery, rest day)
- Workout goal/target
- Distance range (optional)
- Time range (optional)
- Zone distribution (optional)
- Target training zone (optional)

**Your job is to DESIGN and CREATE a complete, detailed workout plan** with:
1. Structured warmup segments
2. Main workout segments (intervals, tempo blocks, easy running)
3. Cool-down segments
4. Specific pacing targets, durations, and PRE scores for each segment

## WorkoutPlan Output Schema

You MUST generate a workout plan with the following structure:

- **title**: string - Concise, descriptive workout name (e.g., "VO2max 800m Repeats", "Easy Aerobic Run")
- **description**: string - Workout purpose and key focus areas (2-3 sentences explaining the training stimulus)
- **detail**: array of workout segments:
  - **segment**: { type: "segment", duration: number (minutes, minimum 0.1), distance_range?: {min, max} (km, optional), intensity_metric: "pace" | "power" | "heart_rate", target_range: {min, max}, description: string, pre: number (0-10 RPE scale) }
  - **loop_start**: { type: "loop_start", id: string, repeat: number (≥1) } - Start of interval/repeat block
  - **loop_end**: { type: "loop_end", id: string } - End of interval/repeat block (must match loop_start id)
- **estimated_tss**: number | null - Training Stress Score (use TSS estimation tool if available, otherwise estimate)
- **total_time**: number | null - Total workout duration in minutes
- **total_distance**: number | null - Total workout distance in kilometers

## Design Principles

Use tools when available:
- Call TSS estimation tools to calculate estimated_tss if available
- Use athlete profile data to personalize pacing targets

## Critical Rules

1. **ALWAYS generate a complete workout** - never return "No workout provided" or parsing errors
2. **For rest days**: Return minimal plan with title, description, empty detail array, and null metrics
3. **Match the requested workout type** - if asked for "easy run", design an easy run; if "intervals", design intervals
4. **Be practical** - workouts should be immediately executable by the athlete
5. **Use realistic pacing** - reference the athlete profile for appropriate pace ranges

You are a GENERATOR, not a PARSER. Create detailed, actionable workout plans from the specifications provided.`},
    model: currentModel,
    // Note: experimental_output schema is removed when used in agent networks
    // The agent should return JSON in text format following the schema described in instructions
    tools: async ({ runtimeContext }) => {
      const accessToken = runtimeContext.get("accessToken") as string | undefined;
      if (!accessToken) {
        console.warn("⚠️ No access token found in runtime context - tools will be empty until authentication");
        return {};
      }
      // Check cache first
      if (toolsCache.has(accessToken)) {
        console.log("✅ Using cached PeakFlow tools");
        return toolsCache.get(accessToken);
      }

      try {
        // Use the correct MCP endpoint - /mcp not /workout-mcp
        const apiBaseUrl = getApiBaseUrl();
        const mcpClient = await createMcpClientWithToken(accessToken, apiBaseUrl, '/mcp');

        // Get tools from the authenticated client
        const tools = await mcpClient.getTools();
        console.log(`✅ Workout expert dynamically loaded ${Object.keys(tools).length} PeakFlow tools`);

        // Cache for this token
        toolsCache.set(accessToken, tools);

        return tools;
      } catch (error) {
        console.error("❌ Failed to load PeakFlow tools:", error);
        if (error instanceof Error) {
          console.error("Error details:", error.message);
        }
        return {};
      }
    }
  });
}

export const workoutExpert = createWorkoutExpert()
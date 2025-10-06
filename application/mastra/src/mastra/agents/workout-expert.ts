import { Agent } from "@mastra/core/agent";
import { currentModel } from "../model";
import { createMcpClientWithToken } from "../mcp/peakflow-client";
import { getApiBaseUrl } from "./utils";
import { WorkoutPlanSchema } from "../type";


export function createWorkoutExpert() {
  console.log("🏃‍♂️ Creating Dynamic Workout Expert...");

  return new Agent({
    id: "workoutExpert",
    name: "workoutExpert",
    description: "Creates structured, data-driven running workout plans based on athlete goals, fitness levels, and training preferences. Optimized for both single-day workouts and multi-day weekly plans.",
    instructions: `You are a world-class workout expert and running coach. You design scientifically-sound, practical running workouts that follow the WorkoutPlan schema.

## WorkoutPlan Schema

- title: string (concise, descriptive workout name)
- description: string (workout purpose and key focus areas)
- detail: array of workout items:
  - segment: { type: "segment", duration (minutes >= 0.1), optional distance_range {min,max} (km), intensity_metric ("pace" | "power" | "heart_rate"), target_range {min,max}, description, pre (0-10) }
  - loop_start: { type: "loop_start", id: string, repeat: number >= 1 }
  - loop_end: { type: "loop_end", id: string }
- estimated_tss: number (Training Stress Score)
- total_time: number (minutes)
- total_distance: number (kilometers)

## Design Principles

**1. Evidence-based structure:**
- Every workout includes proper warm-up (10-15 min easy)
- Main work follows specific training stimulus (intervals, tempo, easy, long run)
- Cool-down period (5-10 min easy recovery)

**2. Intensity targeting:**
- pace: Use seconds/km format (e.g., 240-300 for 4:00-5:00 /km)
- power: Use watts (e.g., 250-280)
- heart_rate: Use bpm (e.g., 140-160)
- Choose metric based on workout type and available data

**3. Progressive overload:**
- Respect athlete's current fitness level
- Build duration/intensity gradually
- Consider recovery needs between hard sessions

**4. Daily plan context:**
When generating plans for weekly workflows:
- Consider previous_workout to ensure proper recovery
- Vary intensity across days (hard/easy principle)
- Align workout_type with weekly training goals
- Use zone_distribution and target_zone when specified

**5. Practical execution:**
- Clear segment descriptions
- Realistic time/distance ranges
- PRE scores (0-10) reflect intended effort
- Loop structures for interval work

## Response Format

The agent is called with structuredOutput schema, so return the complete WorkoutPlan object matching the schema. The system will validate it automatically.

Always aim to produce practical, immediately-implementable workouts that athletes can execute confidently.`,
    model: currentModel,
    // Note: experimental_output schema is removed when used in agent networks
    // The agent should return JSON in text format following the schema described in instructions
    tools: async ({ runtimeContext }) => {
      const accessToken = runtimeContext.get("accessToken") as string | undefined;
      if (!accessToken) {
        console.warn("⚠️ No access token found in runtime context - tools will be empty until authentication");
        return {};
      }
      
      try {
        // Use the correct MCP endpoint - /mcp not /workout-mcp
        const apiBaseUrl = getApiBaseUrl();
        const mcpClient = await createMcpClientWithToken(accessToken, apiBaseUrl, '/mcp');

        // Get tools from the authenticated client
        const tools = await mcpClient.getTools();
        console.log(`✅ Workout expert dynamically loaded ${Object.keys(tools).length} PeakFlow tools`);

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
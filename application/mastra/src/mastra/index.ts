import { Mastra } from '@mastra/core/mastra';
import { PostgresStore } from '@mastra/pg';
import { workoutExpert } from './agents/workout-expert';
import { phasePlanner } from './agents/phase-planner';
import { workoutEnhancer } from './agents/workout-enhancer';
import { Memory } from '@mastra/memory';
import { Agent } from '@mastra/core/agent';
import { currentModel } from "./model";
import { generateDetailedWorkoutsWorkflow } from './workflows/generateDetailedWorkoutsWorkflow';
import { runningPhaseWorkflow } from './workflows/runningPhaseWorkflow';
import { PinoLogger } from '@mastra/loggers';
const connectionString = `postgresql://${process.env.DB_USER}:${process.env.DB_PASSWORD}@${process.env.DB_HOST}:${process.env.DB_PORT}/${process.env.DB_NAME}`;
const logger = new PinoLogger();

export function createRunningCoachAgentWithToken(postgresStore: PostgresStore) {
  logger.info("🏃‍♂️ Creating Dynamic Running Coach Agent...");

  // Always use the provided PostgresStore to avoid duplicate connections
  const storage = postgresStore;

  // Create memory instance for this agent
  const memory = new Memory({
    storage,
    options: {
      lastMessages: 5,
      threads: {
        generateTitle: true
      },
      workingMemory: {
        enabled: true,
        scope: 'resource',
        template: `# Running Coach Memory

## Athlete Profile
- Name:
- Experience Level: [Beginner/Intermediate/Advanced]
- Primary Goals:
- Current Training Phase:

## Physical Metrics
- Heart Rate Zones:
- Recent Race Times:
- Injury History:

## Training Preferences
- Preferred Training Days:
- Available Training Time:

## Recent Sessions
- Last Workout Notes:
- Current Weekly Mileage:
- Recovery Status:

## Phase Plan Progress
- Active Training Plan: [Yes/No]
- Plan Start Date:
- Target Race Date:
- Current Phase: [e.g., Base Week 3, Build Week 1]
- Total Phases Generated:

## Workout Detail Status
Use this section to track which weeks have detailed workouts generated:

### Completed Weeks (with full workout details):
- [List week IDs that have been populated, e.g., "base-week-1", "base-week-2"]

### Pending Weeks (need workout details):
- [List week IDs that still need workouts generated]
- Priority: Next 4 weeks always maintained

### Notes:
- Maintain rolling 4-week detailed workout buffer
- When athlete completes a week, generate next week's details
- Track which critical workouts have been converted to full plans
`,
      },
    },
  });

  return new Agent({
    id: "runningCoach",
    name: "runningCoach",
    description: "Expert running coach with access to athlete performance data, training history, and personalized memory. Provides periodized training plans and workout programming using specialized workflows with intelligent progress tracking.",
    workflows: {
      runningPhaseWorkflow,
      generateDetailedWorkoutsWorkflow
    },
    instructions: () => {
      return `
You are an expert running coach with access to fitness data and conversation history.

## Core Principles
- Provide clear, actionable coaching based on actual data
- Update working memory as you learn about the athlete
- NEVER explain system mechanics, workflow states, or technical processes to the athlete
- Ask for information conversationally when needed
- Focus on analyzing athlete data and providing guidance based on training principles

## Memory Management
Update working memory when learning:
- Athlete profile (name, experience, goals, current phase)
- Performance metrics (HR zones, race times, thresholds)
- Training preferences and constraints
- Phase plan progress (active plan, completed/pending weeks)

## Training Plan Development with Workflows

When athlete requests a training plan, use workflows in this TWO-STEP sequential process:

### Step 1: Use runningPhaseWorkflow
First, collect required information (ask conversationally if not in memory):
- Race schedule with at least one A-priority race (date, distance, priority, optional name)
- Target race distance in km
- Current weekly mileage in km
- Experience level: beginner, intermediate, or advanced
- Available training days per week: 3-7 days

Execute **runningPhaseWorkflow** with complete athlete data. It returns:
- Structured periodized training phases
- Week-by-week breakdown with start/end dates
- Weekly focus and training objectives
- High-level critical workout descriptions for each week
- Recovery week placement

### Step 2: Use generateDetailedWorkoutsWorkflow (Sequential - after Step 1)
After runningPhaseWorkflow completes:

1. **Extract critical workouts from weeks 1-4** of the returned phases
2. **Execute generateDetailedWorkoutsWorkflow FOR EACH WEEK** sequentially, NEVER in parallel:

The workflow returns fully detailed workout prescriptions with:
- Specific segments (warmup, intervals, cooldown)
- Precise pacing and heart rate zones
- Duration and distance for each segment
- Execution instructions and coaching cues

**CRITICAL Workflow Usage Rules**:
- Execute generateDetailedWorkoutsWorkflow sequentially AFTER runningPhaseWorkflow
- ONLY process weeks 1-4 initially to maintain a rolling buffer
- NEVER run workflows in parallel or out of order
- NEVER generate more than 7 workouts in a single call

### After Both Workflows Complete:
- Update memory: "Active Training Plan: Yes", "Completed Weeks: week-1, week-2, week-3, week-4"
- **Summarize plan to athlete with context**

## Communication Rules

**NEVER say:**
- "I need to check the system..."
- "Processing your request..."
- Any technical explanations about internal processes

**ALWAYS:**
- Ask for information naturally: "What's your race date and distance?"
- Present results directly: "Here's your 12-week training plan..."
- Give coaching context: "This week builds aerobic endurance..."
- Speak as a coach, not as a system
  `;
    },
    model: currentModel,
    memory: memory
  });
}

// Shared PostgresStore instance - eliminates duplicate connection warnings
export const sharedPostgresStore = new PostgresStore({
  connectionString,
});

const runningCoach = createRunningCoachAgentWithToken(sharedPostgresStore)

console.log("Using PostgreSQL connection string:", connectionString);

// Create Mastra instance with agents and workflows
export const mastra = new Mastra({
  agents: {
    runningCoach,
    workoutExpert,
    phasePlanner,
    workoutEnhancer
  },
  workflows: {
    runningPhaseWorkflow,
    generateDetailedWorkoutsWorkflow
  },
  storage: sharedPostgresStore,
  logger: logger
});
// Export the agent creation functions
export { createWorkoutExpert } from './agents/workout-expert';
export { createAuthenticatedPeakflowClient, createMcpClientWithToken } from './mcp/peakflow-client';
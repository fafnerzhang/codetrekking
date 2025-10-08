import { createStep, createWorkflow } from '@mastra/core/workflows';
import { z } from 'zod';
import { RaceEventSchema, TrainingPhaseSchema } from '../type';
import logger from '../../logger';

// Single step: Generate structured training phases from input data
const generateTrainingPhases = createStep({
  id: 'generate-training-phases',
  description: 'Generate structured periodized training phases based on athlete requirements',
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
  execute: async ({ inputData, mastra, runtimeContext, writer }) => {
    const {
      race_schedule,
      target_distance,
      current_weekly_mileage,
      experience_level,
      available_days_per_week,
    } = inputData;
    logger.info('Input Data:', inputData);
    logger.info('Running generateTrainingPhases step');
    logger.info('RuntimeContext coachId:', runtimeContext?.get('coachId') || 'NOT SET - using default');

    // Get phase planner agent
    const agent = mastra?.getAgent('phasePlanner');
    if (!agent) {
      throw new Error('phasePlanner agent not found');
    }

    // Find A-priority race
    const aPriorityRaces = race_schedule.filter(r => r.priority === 'A');
    if (aPriorityRaces.length === 0) {
      throw new Error('At least one A-priority race is required');
    }

    const primaryRace = aPriorityRaces[0];
    const today = new Date();
    // Ensure race date is a Date object
    const raceDate = primaryRace.date instanceof Date ? primaryRace.date : new Date(primaryRace.date);
    const weeksToRace = Math.ceil((raceDate.getTime() - today.getTime()) / (7 * 24 * 60 * 60 * 1000));

    // Build comprehensive prompt for structured phase generation
    const prompt = `Create a complete periodized training plan with the following parameters:

**Primary Goal:**
- Target Race: ${primaryRace.name || 'Goal Race'} on ${raceDate.toISOString().split('T')[0]}
- Distance: ${target_distance} km
- Weeks Available: ${weeksToRace}

**Race Schedule:**
${race_schedule.map(r => {
  const rDate = r.date instanceof Date ? r.date : new Date(r.date);
  return `- ${r.priority}-Priority: ${r.distance}km on ${rDate.toISOString().split('T')[0]}${r.name ? ` (${r.name})` : ''}`;
}).join('\n')}

**Athlete Profile:**
- Experience Level: ${experience_level}
- Current Weekly Mileage: ${current_weekly_mileage} km
- Available Training Days: ${available_days_per_week} per week

**REQUIRED OUTPUT:**

You MUST generate a structured training plan array with multiple phases. Each phase must include:

1. Phase metadata:
   - phase_id: Unique identifier (e.g., "build-phase", "peak-phase")
   - name: Full phase name (e.g., "Base Building", "Build Phase", "Peak Phase", "Taper")
   - tag: Short identifier (e.g., "base", "build", "peak", "taper")
   - description: Training objectives and focus for this phase
   - **workout_focus: MANDATORY ARRAY - EVERY PHASE MUST HAVE THIS FIELD**
     * Base phase example: ["aerobic base", "easy volume"]
     * Build phase example: ["threshold", "VO2max"]
     * Peak phase example: ["race pace", "speed endurance"]
     * Taper phase example: ["freshness", "sharpness"]

2. Week-by-week breakdown for each phase:
   - Each week needs: week_id (e.g., "week-1"), phase_id (matching parent phase), start_date (ISO string), end_date (ISO string), description
   - weekly_mileage: Number or null/omit if not specified
   - Each week needs 2-3 critical_workouts array with objects containing: id and description

3. The entire plan duration must fit within the ${weeksToRace} weeks leading up to the primary race.

**CRITICAL VALIDATION RULES:**
- EVERY phase object MUST include the "workout_focus" field as an array with at least 1 element
- Missing workout_focus will cause validation failure
- Dates should be ISO strings (YYYY-MM-DD format)

**Correct Example - ALL phases have workout_focus:**
{
  "phases": [
    {
      "phase_id": "base-phase",
      "name": "Base Building",
      "tag": "base",
      "description": "Build aerobic foundation",
      "workout_focus": ["aerobic base", "easy volume"],
      "weeks": [...]
    },
    {
      "phase_id": "build-phase",
      "name": "Build Phase",
      "tag": "build",
      "description": "Increase intensity",
      "workout_focus": ["threshold", "VO2max"],
      "weeks": [...]
    }
  ]
}

Start from today's date (${today.toISOString().split('T')[0]}) and work forward ${weeksToRace} weeks to reach the race.

Generate the complete phase array now with workout_focus in EVERY phase.`;

    // Generate structured phases directly
    logger.info(`Phase Workflow runtimeContext: ${JSON.stringify(runtimeContext)}`);

    // Use agent.generate instead of agent.stream for better error handling with structured output
    const result = await agent.generate(
      [{ role: 'user', content: prompt }],
      {
        structuredOutput: {
          schema: z.object({
            phases: z.array(TrainingPhaseSchema),
          }),
        },
        runtimeContext: runtimeContext
      }
    );

    if (!result.object) {
      logger.error('❌ phasePlanner failed to generate structured output');
      throw new Error('Failed to generate training phases: Invalid structured output from phasePlanner');
    }

    const object = result.object;

    // Validate result
    if (!object || !object.phases || object.phases.length === 0) {
      logger.error('LLM returned empty or invalid phases array', { object });
      throw new Error('Failed to generate training phases: LLM returned empty result');
    }

    // Validate that ALL phases have workout_focus (schema validation should catch this, but double-check)
    const phasesWithoutFocus = object.phases.filter(p => !p.workout_focus || p.workout_focus.length === 0);
    if (phasesWithoutFocus.length > 0) {
      const missingPhases = phasesWithoutFocus.map(p => p.phase_id).join(', ');
      logger.error(`❌ Phases missing workout_focus: ${missingPhases}`);
      logger.error('Generated phases:', JSON.stringify(object.phases, null, 2));
      throw new Error(`Invalid phase structure: The following phases are missing workout_focus field: ${missingPhases}. Every phase MUST have workout_focus array with at least 1 element.`);
    }

    logger.info(`Generated ${object.phases.length} training phases`);

    logger.info('✅ Training phases generated successfully');
    return {
      phases: object.phases,
    };
  },
});

// Step to save phases to database via API
const saveToDatabase = createStep({
  id: 'save-to-database',
  description: 'Save generated training phases to database using bulk API endpoint',
  inputSchema: z.object({
    phases: z.array(TrainingPhaseSchema),
  }),
  outputSchema: z.object({
    phases: z.array(TrainingPhaseSchema),
  }),
  execute: async ({ inputData, runtimeContext }) => {
    const { phases } = inputData;

    // Get accessToken from runtime context
    const accessToken = runtimeContext?.get('accessToken');
    if (!accessToken) {
      logger.warn('accessToken not found in runtimeContext - skipping database save');
      return { phases }; // Return phases without saving
    }

    if (!phases || phases.length === 0) {
      throw new Error('No phases to save');
    }

    logger.info(`Saving ${phases.length} phases to database`);

    const apiUrl = process.env.API_BASE_URL || 'http://localhost:8002';

    // Save each phase separately (bulk endpoint saves phase + weeks atomically)
    for (const phase of phases) {
      try {
        // Send exactly as type.ts structure - no transformation
        const requestBody = {
          // user_id omitted - API will use authenticated user from token
          phase_id: phase.phase_id,
          name: phase.name,
          tag: phase.tag,
          description: phase.description,
          workout_focus: phase.workout_focus,
          weeks: phase.weeks, // Keep original structure
        };

        logger.info(`Saving phase ${phase.phase_id} with ${phase.weeks.length} weeks`);

        const response = await fetch(`${apiUrl}/training-plans/phases/bulk`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${accessToken}`,
          },
          body: JSON.stringify(requestBody),
        });

        if (!response.ok) {
          const errorText = await response.text();
          logger.error(`Failed to save phase ${phase.phase_id}: ${response.status} - ${errorText}`);
          throw new Error(`API error saving phase ${phase.phase_id}: ${response.status} - ${errorText}`);
        }

        const savedPhase = await response.json();
        logger.info(`✅ Saved phase ${phase.phase_id} successfully`);
      } catch (error) {
        logger.error(`Error saving phase ${phase.phase_id}:`, error);
        throw error;
      }
    }

    logger.info(`✅ All ${phases.length} phases saved to database`);

    // Return original phases (maintain workflow output)
    return {
      phases: phases,
    };
  },
});

// Main workflow
export const runningPhaseWorkflow = createWorkflow({
  id: 'running-phase-workflow',
  description: 'Generate a complete periodized training plan with structured phases (Base, Build, Peak, Taper). Creates week-by-week progression with training focus areas, recovery weeks, and critical workout outlines based on athlete profile and race schedule. Returns high-level phase structure that can be used to generate detailed workout prescriptions.',
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
})
  .then(generateTrainingPhases)
  .then(saveToDatabase)
  .commit();

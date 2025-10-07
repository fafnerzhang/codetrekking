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
   - workout_focus: REQUIRED array with at least one focus area (e.g., ["aerobic base", "easy volume"] for base phase, ["threshold", "VO2max"] for build, ["race pace", "speed"] for peak, ["freshness", "sharpness"] for taper)

2. Week-by-week breakdown for each phase:
   - Each week needs: id (e.g., "week-1"), phase_id (matching parent phase), start_date (ISO string), end_date (ISO string), description
   - weekly_mileage: Number or null/omit if not specified
   - Each week needs 2-3 critical_workouts array with objects containing: id and description
3. The entire plan duration must fit within the ${weeksToRace} weeks leading up to the primary race.

IMPORTANT: Return valid JSON matching the schema. Dates should be ISO strings (YYYY-MM-DD format).

**Example structure you must follow:**
- Phase 1 (Base): Weeks 1-4 with aerobic foundation workouts
- Phase 2 (Build): Weeks 5-8 with threshold and interval work
- Phase 3 (Peak): Weeks 9-10 with race-specific intensity
- Phase 4 (Taper): Week 11 with volume reduction

Start from today's date (${today.toISOString().split('T')[0]}) and work forward ${weeksToRace} weeks to reach the race.

Generate the complete phase array now.`;

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

    logger.info(`Generated ${object.phases.length} training phases`);

    logger.info('✅ Training phases generated successfully');
    return {
      phases: object.phases,
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
  .commit();

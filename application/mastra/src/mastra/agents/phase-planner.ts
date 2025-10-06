import { Agent } from "@mastra/core/agent";
import { currentModel } from "../model";
import { calendarTool, calculatorTool } from "../tools/utility-tools";
import { generateCoachingInstructions } from "../utils/coaches";


export function createPhasePlanner() {
  console.log("📅 Creating Phase Planner Agent...");

  return new Agent({
    id: "phasePlanner",
    name: "phasePlanner",
    description: "Expert in training periodization and phase planning for endurance athletes. Designs structured training phases with progressive overload, specificity, and proper tapering.",
    instructions: ({ runtimeContext }) => {
      const coachingInstructions = generateCoachingInstructions(runtimeContext);
      return coachingInstructions
    },
    model: currentModel,
    tools: {
      calendarTool,
      calculatorTool,
    },
  });
}

export const phasePlanner = createPhasePlanner();

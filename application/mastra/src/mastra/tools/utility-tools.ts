import { createTool } from "@mastra/core";
import { z } from "zod";

// Helper to get date in Asia/Taipei timezone
function getTaipeiDate(dateString?: string): Date {
  const date = dateString ? new Date(dateString) : new Date();
  // Get UTC time and convert to Taipei (UTC+8)
  const taipeiTime = new Date(date.toLocaleString('en-US', { timeZone: 'Asia/Taipei' }));
  return taipeiTime;
}

// Helper to format date in Asia/Taipei timezone
function formatTaipeiDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export const calendarTool = createTool({
  id: "calendar-tool",
  description: "Get calendar information including current date, day of week, date calculations, and week boundaries. Useful for workout scheduling and date planning.",
  inputSchema: z.object({
    operation: z.enum([
      "current_date",
      "day_of_week",
      "days_between",
      "add_days",
      "week_start_end",
      "weeks_between"
    ]).describe("Calendar operation to perform"),
    date1: z.string().optional().describe("First date (ISO format YYYY-MM-DD)"),
    date2: z.string().optional().describe("Second date (ISO format YYYY-MM-DD)"),
    days: z.number().optional().describe("Number of days to add"),
  }),
  outputSchema: z.object({
    result: z.union([
      z.string(),
      z.number(),
      z.object({
        monday: z.string(),
        sunday: z.string(),
      }),
    ]),
    details: z.string().optional(),
  }),
  execute: async ({ context }) => {
    const { operation, date1, date2, days } = context;

    switch (operation) {
      case "current_date": {
        const now = getTaipeiDate();
        const dateStr = formatTaipeiDate(now);
        return {
          result: dateStr,
          details: `Current date in Asia/Taipei: ${dateStr}`,
        };
      }

      case "day_of_week": {
        if (!date1) throw new Error("date1 required for day_of_week");
        const d = getTaipeiDate(date1);
        const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
        return {
          result: dayNames[d.getDay()],
          details: `${date1} is a ${dayNames[d.getDay()]} in Asia/Taipei timezone`,
        };
      }

      case "days_between": {
        if (!date1 || !date2) throw new Error("date1 and date2 required for days_between");
        const d1 = getTaipeiDate(date1);
        const d2 = getTaipeiDate(date2);
        const diffTime = Math.abs(d2.getTime() - d1.getTime());
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        return {
          result: diffDays,
          details: `${diffDays} days between ${date1} and ${date2} (Asia/Taipei timezone)`,
        };
      }

      case "add_days": {
        if (!date1 || days === undefined) throw new Error("date1 and days required for add_days");
        const d = getTaipeiDate(date1);
        d.setDate(d.getDate() + days);
        const resultDate = formatTaipeiDate(d);
        return {
          result: resultDate,
          details: `${date1} + ${days} days = ${resultDate} (Asia/Taipei timezone)`,
        };
      }

      case "week_start_end": {
        if (!date1) throw new Error("date1 required for week_start_end");
        const d = getTaipeiDate(date1);
        const day = d.getDay();
        const diff = d.getDate() - day + (day === 0 ? -6 : 1); // adjust when day is sunday
        const monday = new Date(d);
        monday.setDate(diff);
        const sunday = new Date(monday);
        sunday.setDate(monday.getDate() + 6);
        const mondayStr = formatTaipeiDate(monday);
        const sundayStr = formatTaipeiDate(sunday);
        return {
          result: {
            monday: mondayStr,
            sunday: sundayStr,
          },
          details: `Week containing ${date1}: Monday ${mondayStr} to Sunday ${sundayStr} (Asia/Taipei timezone)`,
        };
      }

      case "weeks_between": {
        if (!date1 || !date2) throw new Error("date1 and date2 required for weeks_between");
        const d1 = getTaipeiDate(date1);
        const d2 = getTaipeiDate(date2);
        const diffTime = Math.abs(d2.getTime() - d1.getTime());
        const weeks = Math.ceil(diffTime / (1000 * 60 * 60 * 24 * 7));
        return {
          result: weeks,
          details: `${weeks} weeks between ${date1} and ${date2} (Asia/Taipei timezone)`,
        };
      }

      default:
        throw new Error(`Unknown operation: ${operation}`);
    }
  },
});

export const calculatorTool = createTool({
  id: "calculator-tool",
  description: "Perform mathematical calculations for training metrics like pace conversions, distance calculations, percentage calculations, and TSS estimations.",
  inputSchema: z.object({
    operation: z.enum([
      "add",
      "subtract",
      "multiply",
      "divide",
      "percentage",
      "pace_to_seconds",
      "seconds_to_pace",
      "average",
      "round"
    ]).describe("Mathematical operation to perform"),
    values: z.array(z.number()).describe("Numbers to calculate with"),
    precision: z.number().optional().describe("Decimal places for rounding (default: 2)"),
  }),
  outputSchema: z.object({
    result: z.number(),
    formula: z.string().optional(),
  }),
  execute: async ({ context }) => {
    const { operation, values, precision = 2 } = context;

    if (values.length === 0) {
      throw new Error("At least one value required");
    }

    let result: number;
    let formula: string;

    switch (operation) {
      case "add":
        result = values.reduce((a, b) => a + b, 0);
        formula = `${values.join(' + ')} = ${result}`;
        break;

      case "subtract":
        if (values.length < 2) throw new Error("At least 2 values required for subtraction");
        result = values.reduce((a, b) => a - b);
        formula = `${values.join(' - ')} = ${result}`;
        break;

      case "multiply":
        result = values.reduce((a, b) => a * b, 1);
        formula = `${values.join(' × ')} = ${result}`;
        break;

      case "divide":
        if (values.length < 2) throw new Error("At least 2 values required for division");
        result = values.reduce((a, b) => a / b);
        formula = `${values.join(' ÷ ')} = ${result}`;
        break;

      case "percentage":
        if (values.length !== 2) throw new Error("Exactly 2 values required for percentage (value, total)");
        result = (values[0] / values[1]) * 100;
        formula = `${values[0]} / ${values[1]} × 100 = ${result}%`;
        break;

      case "pace_to_seconds":
        // Convert min/km to seconds/km (e.g., 5.5 min/km → 330 seconds/km)
        if (values.length !== 1) throw new Error("Exactly 1 value required (minutes per km)");
        result = values[0] * 60;
        formula = `${values[0]} min/km = ${result} sec/km`;
        break;

      case "seconds_to_pace":
        // Convert seconds/km to min/km (e.g., 330 seconds → 5.5 min/km)
        if (values.length !== 1) throw new Error("Exactly 1 value required (seconds per km)");
        result = values[0] / 60;
        formula = `${values[0]} sec/km = ${result.toFixed(2)} min/km`;
        break;

      case "average":
        result = values.reduce((a, b) => a + b, 0) / values.length;
        formula = `Average of [${values.join(', ')}] = ${result}`;
        break;

      case "round":
        if (values.length !== 1) throw new Error("Exactly 1 value required for rounding");
        result = Math.round(values[0] * Math.pow(10, precision)) / Math.pow(10, precision);
        formula = `${values[0]} rounded to ${precision} decimals = ${result}`;
        break;

      default:
        throw new Error(`Unknown operation: ${operation}`);
    }

    // Round result to specified precision
    result = Math.round(result * Math.pow(10, precision)) / Math.pow(10, precision);

    return { result, formula };
  },
});

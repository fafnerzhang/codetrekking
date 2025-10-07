/**
 * User Indicators utility for fetching athlete fitness data
 */

import { RuntimeContext } from "@mastra/core/runtime-context";

export interface UserIndicators {
  user_id: string;
  updated_at: string;

  // Threshold values
  threshold_power?: number;
  threshold_heart_rate?: number;
  threshold_pace?: number;

  // Max values
  max_heart_rate?: number;
  max_power?: number;
  max_pace?: number;

  // Critical thresholds
  critical_speed?: number;

  // VO2 and fitness metrics
  vo2max?: number;
  vdot?: number;

  // Physiological data
  resting_heart_rate?: number;
  weight?: number;
  height?: number;

  // Personal information
  gender?: string;
  birth_date?: string;
  age?: number;

  // Body composition
  body_fat_percentage?: number;
  muscle_mass?: number;

  // Training metrics
  training_stress_score?: number;
  power_to_weight_ratio?: number;
}

/**
 * Fetch user indicators from API service
 */
export async function fetchUserIndicators(accessToken: string, apiBaseUrl: string): Promise<UserIndicators | null> {
  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/analytics/user/indicators`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      if (response.status === 404) {
        console.warn('User indicators not found - user may not have set up indicators yet');
        return null;
      }
      throw new Error(`Failed to fetch user indicators: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    return data as UserIndicators;
  } catch (error) {
    console.error('Error fetching user indicators:', error);
    return null;
  }
}


/**
 * Format user indicators for LLM context
 */
// Make the input of type RuntimeContext
export function formatIndicatorsForLLM(runtimeContext: RuntimeContext): string {
  const indicators = runtimeContext.get('userIndicators') as UserIndicators | null | undefined;
  if (!indicators) {
    return `**User Indicators:** Not available. User has not set up fitness indicators yet.`;
  }

  const sections: string[] = [];

  // Threshold values
  if (indicators.threshold_heart_rate || indicators.threshold_power || indicators.threshold_pace) {
    sections.push(`**Threshold Values:**`);
    if (indicators.threshold_heart_rate) {
      sections.push(`- Lactate Threshold Heart Rate: ${indicators.threshold_heart_rate} BPM`);
    }
    if (indicators.threshold_power) {
      sections.push(`- Threshold Power (FTP): ${indicators.threshold_power} watts`);
    }
    if (indicators.threshold_pace) {
      sections.push(`- Threshold Pace: ${indicators.threshold_pace} min/km`);
    }
  }

  // Max values
  if (indicators.max_heart_rate || indicators.max_power || indicators.max_pace) {
    sections.push(`\n**Maximum Values:**`);
    if (indicators.max_heart_rate) {
      sections.push(`- Max Heart Rate: ${indicators.max_heart_rate} BPM`);
    }
    if (indicators.max_power) {
      sections.push(`- Max Power: ${indicators.max_power} watts`);
    }
    if (indicators.max_pace) {
      sections.push(`- Max Pace: ${indicators.max_pace} min/km`);
    }
  }

  // Fitness metrics
  if (indicators.vo2max || indicators.vdot) {
    sections.push(`\n**Fitness Metrics:**`);
    if (indicators.vo2max) {
      sections.push(`- VO2max: ${indicators.vo2max} ml/kg/min`);
    }
    if (indicators.vdot) {
      sections.push(`- VDOT: ${indicators.vdot}`);
    }
  }

  // Physiological data
  const physioData = [];
  if (indicators.resting_heart_rate) {
    physioData.push(`Resting HR: ${indicators.resting_heart_rate} BPM`);
  }
  if (indicators.weight) {
    physioData.push(`Weight: ${indicators.weight} kg`);
  }
  if (indicators.height) {
    physioData.push(`Height: ${indicators.height} cm`);
  }
  if (indicators.age) {
    physioData.push(`Age: ${indicators.age} years`);
  }
  if (indicators.gender) {
    physioData.push(`Gender: ${indicators.gender}`);
  }

  if (physioData.length > 0) {
    sections.push(`\n**Physiological Data:**`);
    sections.push(`- ${physioData.join(', ')}`);
  }

  // Power to weight ratio
  if (indicators.power_to_weight_ratio) {
    sections.push(`\n**Power to Weight Ratio:** ${indicators.power_to_weight_ratio.toFixed(2)} W/kg`);
  }

  // Training stress
  if (indicators.training_stress_score) {
    sections.push(`\n**Current Training Stress Score:** ${indicators.training_stress_score}`);
  }

  if (sections.length === 0) {
    return `**User Indicators:** Available but no values set. Assume typical values for experience level.`;
  }

  return sections.join('\n');
}

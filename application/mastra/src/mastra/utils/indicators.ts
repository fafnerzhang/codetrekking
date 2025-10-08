/**
 * User Indicators utility for fetching athlete fitness data
 */

import { RuntimeContext } from "@mastra/core/runtime-context";

export interface ZoneInfo {
  zone_number: number;
  zone_name: string;
  range_min: number;
  range_max: number;
  range_unit: string;
  description: string;
  purpose: string;
}

export interface ZoneRanges {
  zone_type: string;
  threshold_value?: number;
  method: string;
  zones: ZoneInfo[];
}

export interface UserZones {
  power_zones?: ZoneRanges;
  pace_zones?: ZoneRanges;
  heart_rate_zones?: ZoneRanges;
}

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
 * Fetch zone distributions from API service
 */
export async function fetchZoneDistributions(
  accessToken: string,
  apiBaseUrl: string,
  days: number = 30
): Promise<ZoneDistributions | null> {
  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/analytics/zone-distributions?days=${days}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      if (response.status === 404) {
        console.warn('Zone distributions not found - user may not have training data yet');
        return null;
      }
      throw new Error(`Failed to fetch zone distributions: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    return data as ZoneDistributions;
  } catch (error) {
    console.error('Error fetching zone distributions:', error);
    return null;
  }
}


/**
 * Format zone ranges for LLM
 */
function formatZoneRanges(zoneRanges: ZoneRanges): string[] {
  const lines: string[] = [];

  for (const zone of zoneRanges.zones) {
    const rangeStr = `${zone.range_min.toFixed(zone.range_unit === 'min/km' ? 2 : 0)}-${zone.range_max.toFixed(zone.range_unit === 'min/km' ? 2 : 0)}${zone.range_unit}`;
    lines.push(`  - Zone ${zone.zone_number} (${zone.zone_name}): ${rangeStr} - ${zone.purpose}`);
  }

  return lines;
}

/**
 * Format user indicators for LLM context
 */
// Make the input of type RuntimeContext
export function formatIndicatorsForLLM(runtimeContext: RuntimeContext): string {
  const indicators = runtimeContext.get('userIndicators') as UserIndicators | null | undefined;
  const userZones = runtimeContext.get('userZones') as UserZones | null | undefined;

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

  // Training Zones from API
  if (userZones) {
    sections.push(`\n**Training Zones:**`);

    if (userZones.heart_rate_zones) {
      sections.push(`\n*Heart Rate Zones (${userZones.heart_rate_zones.method}, LTHR ${userZones.heart_rate_zones.threshold_value} BPM):*`);
      const hrLines = formatZoneRanges(userZones.heart_rate_zones);
      sections.push(...hrLines);
    }

    if (userZones.power_zones) {
      sections.push(`\n*Power Zones (${userZones.power_zones.method}, FTP ${userZones.power_zones.threshold_value}W):*`);
      const powerLines = formatZoneRanges(userZones.power_zones);
      sections.push(...powerLines);
    }

    if (userZones.pace_zones) {
      sections.push(`\n*Pace Zones (${userZones.pace_zones.method}, Threshold ${userZones.pace_zones.threshold_value?.toFixed(2)} min/km):*`);
      const paceLines = formatZoneRanges(userZones.pace_zones);
      sections.push(...paceLines);
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

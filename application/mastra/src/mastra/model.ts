import {google} from "@ai-sdk/google";
import { anthropic } from "@ai-sdk/anthropic";
import { openai } from "@ai-sdk/openai";

export const googleModel = google("gemini-2.5-pro")
export const openaiModel = openai("gpt-5-nano-2025-08-07")
export const anthropicModel = anthropic("claude-3-5-haiku-latest")
export const currentModel = googleModel  
/**
 * tokenpricing — LLM token pricing library for TypeScript.
 *
 * Public API:
 * - getPricing(modelId, currency?) — get pricing info for a model
 * - computeCost(modelId, inputTokens, outputTokens, currency?) — compute total cost
 *
 * Data source: LLMTracker (https://github.com/DiTo97/LLMTracker)
 */

export { getPricing, computeCost } from "./core.js";
export type { PricingInfo } from "./modeling.js";

/**
 * tokenpricing — LLM token pricing library for TypeScript.
 *
 * Public API:
 * - getPricing(modelId, currency?) — get pricing info for a model
 * - computeCost(modelId, inputTokens, outputTokens, currency?, options?) — compute total cost
 *
 * Data source: tokenpricing canonical dataset (https://github.com/Atena-IT/tokenpricing)
 */

export type { ComputeCostOptions } from "./core.js";
export { computeCost, getPricing } from "./core.js";
export type { PricingInfo } from "./modeling.js";

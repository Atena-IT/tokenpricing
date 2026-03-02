/**
 * Public facade API for tokenpricing.
 *
 * Exposes:
 * - getPricing(modelId, currency?) — get pricing info for a model
 * - computeCost(modelId, inputTokens, outputTokens, currency?) — compute total cost
 */

import { getUsdRate } from "./currency.js";
import { type PricingInfo, toPricingInfo } from "./modeling.js";
import { getPricingData } from "./pricing.js";

/**
 * Get pricing info for a specific model.
 */
export async function getPricing(
  modelId: string,
  currency = "USD",
): Promise<PricingInfo> {
  const data = await getPricingData();
  const model = data.models[modelId];

  if (!model) {
    // Lazy import to avoid circular deps at module load
    const { suggestModel } = await import("./suggestions.js");
    const displayNames: Record<string, string> = {};
    for (const [id, m] of Object.entries(data.models)) {
      displayNames[id] = m.display_name;
    }
    const suggestion = suggestModel(
      modelId,
      Object.keys(data.models),
      displayNames,
    );
    if (suggestion) {
      throw new Error(
        `Model not found: ${modelId}. Did you mean '${suggestion.match}'?`,
      );
    }
    throw new Error(`Model not found: ${modelId}`);
  }

  const target = currency.toUpperCase();
  if (target === "USD") {
    return toPricingInfo(model.pricing);
  }

  const rate = await getUsdRate(target);
  return {
    inputPerMillion: model.pricing.input_per_million * rate,
    outputPerMillion: model.pricing.output_per_million * rate,
    currency: target,
  };
}

/**
 * Compute total cost for a specific model given token counts.
 */
export async function computeCost(
  modelId: string,
  inputTokens: number,
  outputTokens: number,
  currency = "USD",
): Promise<number> {
  if (inputTokens < 0 || outputTokens < 0) {
    throw new Error("Token counts must be non-negative");
  }

  const pricing = await getPricing(modelId, currency);
  const perMillion = 1_000_000;
  const inputCost = (inputTokens / perMillion) * pricing.inputPerMillion;
  const outputCost = (outputTokens / perMillion) * pricing.outputPerMillion;
  return inputCost + outputCost;
}

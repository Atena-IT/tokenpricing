/**
 * Fetch and cache LLM pricing data from LLMTracker.
 *
 * Data source: https://github.com/DiTo97/LLMTracker
 */

import { TtlCache } from "./cache.js";
import { type RawPricingData, parsePricingData } from "./modeling.js";

/** LLMTracker data URL — updated every 6 hours */
const LLMTRACKER_URL =
  "https://raw.githubusercontent.com/DiTo97/LLMTracker/main/data/current/prices.json";

/** Cache TTL: 6 hours (21600000 ms) — aligns with LLMTracker update frequency */
const CACHE_TTL_MS = 6 * 60 * 60 * 1000;

async function fetchPricingData(): Promise<RawPricingData> {
  const response = await fetch(LLMTRACKER_URL);
  if (!response.ok) {
    throw new Error(
      `Failed to fetch pricing data: ${response.status} ${response.statusText}`,
    );
  }
  const data: unknown = await response.json();
  return parsePricingData(data);
}

const pricingCache = new TtlCache<RawPricingData>(
  CACHE_TTL_MS,
  fetchPricingData,
);

/**
 * Get pricing data with caching (6h TTL).
 */
export async function getPricingData(
  forceRefresh = false,
): Promise<RawPricingData> {
  return pricingCache.get(forceRefresh);
}

/**
 * Clear the pricing data cache (used in tests).
 */
export function clearPricingCache(): void {
  pricingCache.clear();
}

/**
 * Fetch and cache canonical pricing data from tokenpricing.
 *
 * Data source: https://github.com/Atena-IT/tokenpricing
 *
 * When `TOKENPRICING_USE_SQLITE=1` (or `true` / `yes`, case-insensitive) is
 * set, pricing data is loaded from a locally-cached SQLite database instead of
 * the full JSON blob. The SQLite path is Node.js only and requires the optional
 * `better-sqlite3` peer dependency. Any failure in the SQLite path causes a
 * transparent fallback to the HTTP-JSON path.
 */

import { TtlCache } from "./cache.js";
import { parsePricingData, type RawPricingData } from "./modeling.js";
import {
  getAllPricingData,
  isSqliteEnabled,
  SQLiteBackendError,
} from "./sqlite-backend.js";

/** Canonical pricing data URL — updated every 6 hours */
const CANONICAL_DATASET_URL =
  "https://raw.githubusercontent.com/Atena-IT/tokenpricing/main/database/current/prices.json";

/** Cache TTL: 6 hours (21600000 ms) — aligns with canonical database refresh frequency */
const CACHE_TTL_MS = 6 * 60 * 60 * 1000;

async function fetchPricingData(): Promise<RawPricingData> {
  // Try SQLite backend first when opted in
  if (isSqliteEnabled()) {
    try {
      return await getAllPricingData();
    } catch (err) {
      if (err instanceof SQLiteBackendError) {
        // Transparent fallback to JSON
        console.warn(
          `[tokenpricing] SQLite backend failed, falling back to JSON: ${err.message}`,
        );
      } else {
        throw err;
      }
    }
  }

  const response = await fetch(CANONICAL_DATASET_URL);
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

/**
 * Currency utilities with 24h cached USD base rates.
 *
 * Fetches USD-based currency rates from the JSDelivr currency API and caches
 * the uppercased mapping for 24 hours.
 */

import { TtlCache } from "./cache.js";

const FOREX_TTL_MS = 24 * 60 * 60 * 1000;
const FOREX_BASE = "usd";
const FOREX_ENDPOINT = `https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/${FOREX_BASE}.json`;

type UsdRates = Record<string, number>;

async function fetchUsdRates(): Promise<UsdRates> {
  const response = await fetch(FOREX_ENDPOINT);
  if (!response.ok) {
    throw new Error(
      `Failed to fetch USD rates: ${response.status} ${response.statusText}`,
    );
  }
  const data = (await response.json()) as Record<string, unknown>;
  const inner = data[FOREX_BASE];

  if (typeof inner !== "object" || inner === null) {
    throw new Error("Invalid forex data: missing USD rates");
  }

  const rates: UsdRates = {};
  for (const [code, val] of Object.entries(inner as Record<string, unknown>)) {
    if (typeof val === "number") {
      rates[code.toUpperCase()] = val;
    }
  }
  return rates;
}

const ratesCache = new TtlCache<UsdRates>(FOREX_TTL_MS, fetchUsdRates);

/**
 * Return mapping of currency code -> rate for 1 USD (cached 24h).
 */
export async function getUsdRates(forceRefresh = false): Promise<UsdRates> {
  return ratesCache.get(forceRefresh);
}

/**
 * Get conversion rate for 1 USD -> target currency.
 */
export async function getUsdRate(currency: string): Promise<number> {
  const code = currency.toUpperCase();
  if (code === "USD") {
    return 1;
  }

  const rates = await getUsdRates();
  if (code in rates) {
    return rates[code];
  }

  // Lazy import to avoid circular deps
  const { suggestCurrency } = await import("./suggestions.js");
  const match = suggestCurrency(code, Object.keys(rates));
  if (match) {
    throw new Error(
      `Unsupported currency: ${currency}. Did you mean '${match.match}'?`,
    );
  }
  throw new Error(`Unsupported currency: ${currency}`);
}

/**
 * Clear the rates cache (used in tests).
 */
export function clearRatesCache(): void {
  ratesCache.clear();
}

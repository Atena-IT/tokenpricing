/**
 * Data models for LLM pricing information from LLMTracker.
 *
 * Internal types match the raw JSON (snake_case).
 * Public PricingInfo uses camelCase.
 */

// --- Public types (camelCase) ---

export interface PricingInfo {
  inputPerMillion: number;
  outputPerMillion: number;
  currency: string;
}

// --- Internal types matching raw JSON (snake_case) ---

export interface RawSourceInfo {
  price_input: number;
  price_output: number;
  last_updated: string;
}

export interface RawPricingInfo {
  input_per_million: number;
  output_per_million: number;
  currency: string;
}

export interface RawModelInfo {
  provider: string;
  model_id: string;
  display_name: string;
  pricing: RawPricingInfo;
  context_window: number;
  max_output_tokens: number;
  model_type: string;
  supports_vision: boolean;
  supports_function_calling: boolean;
  supports_streaming: boolean;
  category: string;
  sources: Record<string, RawSourceInfo>;
  affiliate_links: Record<string, string>;
}

export interface RawProviderInfo {
  name: string;
  website: string;
  pricing_page: string;
  affiliate_link: string;
}

export interface RawMetadataInfo {
  total_models: number;
  sources: string[];
  last_scrape: string;
  categories: Record<string, number>;
}

export interface RawPricingData {
  generated_at: string;
  models: Record<string, RawModelInfo>;
  providers: Record<string, RawProviderInfo>;
  metadata: RawMetadataInfo;
}

/**
 * Parse raw JSON into typed PricingData.
 * Performs basic shape validation.
 */
export function parsePricingData(data: unknown): RawPricingData {
  if (typeof data !== "object" || data === null) {
    throw new Error("Invalid pricing data: expected object");
  }

  const obj = data as Record<string, unknown>;

  if (typeof obj.generated_at !== "string") {
    throw new Error("Invalid pricing data: missing generated_at");
  }
  if (typeof obj.models !== "object" || obj.models === null) {
    throw new Error("Invalid pricing data: missing models");
  }
  if (typeof obj.providers !== "object" || obj.providers === null) {
    throw new Error("Invalid pricing data: missing providers");
  }
  if (typeof obj.metadata !== "object" || obj.metadata === null) {
    throw new Error("Invalid pricing data: missing metadata");
  }

  return data as RawPricingData;
}

/**
 * Convert raw model pricing to public PricingInfo.
 */
export function toPricingInfo(
  raw: RawPricingInfo,
  currency?: string,
): PricingInfo {
  return {
    inputPerMillion: raw.input_per_million,
    outputPerMillion: raw.output_per_million,
    currency: currency ?? raw.currency,
  };
}

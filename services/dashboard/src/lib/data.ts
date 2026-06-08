const CANONICAL_DATA_ROOT =
  "https://raw.githubusercontent.com/Atena-IT/tokenpricing/main/data";

export interface RawPricingInfo {
  input_per_million: number;
  output_per_million: number;
  cache_read_per_million: number | null;
  cache_creation_per_million: number | null;
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
}

export interface RawPricingData {
  generated_at: string;
  models: Record<string, RawModelInfo>;
}

interface ChangelogSummary {
  model_additions: number;
  model_removals: number;
  pricing_changes: number;
  cache_price_changes: number;
}

interface ChangelogChange {
  type: string;
  model_id: string;
  model_type?: string | null;
}

export interface ChangelogData {
  generated_at: string;
  summary: ChangelogSummary;
  changes: ChangelogChange[];
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${CANONICAL_DATA_ROOT}/${path}`);
  if (!response.ok) {
    throw new Error(`Failed to load ${path}: ${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export function loadPricingData() {
  return fetchJson<RawPricingData>("current/prices.json");
}

export function loadChangelogData() {
  return fetchJson<ChangelogData>("changelog/latest.json");
}

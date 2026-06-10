import { deriveModelName, formatProvider } from "./utils";

const DEFAULT_CANONICAL_DATA_ROOT =
  "https://raw.githubusercontent.com/Atena-IT/tokenpricing/main/database";
const CANONICAL_DATA_ROOT =
  (import.meta.env.VITE_CANONICAL_DATA_ROOT?.trim() || DEFAULT_CANONICAL_DATA_ROOT).replace(/\/+$/, "");

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

/** Raw record enriched with display-ready fields derived once at load time. */
export interface ModelRow extends RawModelInfo {
  name: string;
  providerLabel: string;
}

export function normalizeModels(data: RawPricingData): ModelRow[] {
  return Object.values(data.models)
    .map((model) => ({
      ...model,
      name: deriveModelName(model),
      providerLabel: formatProvider(model.provider),
    }))
    .sort((left, right) => left.name.localeCompare(right.name, "en-US"));
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

const GITHUB_RAW_PATTERN = /^https:\/\/raw\.githubusercontent\.com\/([^/]+)\/([^/]+)\/([^/]+)\/(.+)$/;
const HISTORY_SNAPSHOT_PATTERN = /^prices-(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z\.json$/;

export interface HistorySnapshot {
  /** ISO timestamp parsed from the snapshot filename. */
  timestamp: string;
  models: Record<string, RawModelInfo>;
}

/**
 * Snapshots live as timestamped files in `database/history/`; the directory
 * listing comes from the GitHub contents API (the raw CDN cannot list).
 * Returns the most recent `limit` snapshots in chronological order.
 */
export async function loadHistorySnapshots(limit = 12): Promise<HistorySnapshot[]> {
  const match = CANONICAL_DATA_ROOT.match(GITHUB_RAW_PATTERN);
  if (!match) {
    return [];
  }
  const [, owner, repo, branch, basePath] = match;
  const listingUrl = `https://api.github.com/repos/${owner}/${repo}/contents/${basePath}/history?ref=${branch}`;
  const response = await fetch(listingUrl);
  if (!response.ok) {
    throw new Error(`Failed to list history snapshots: ${response.status} ${response.statusText}`);
  }
  const entries = (await response.json()) as Array<{ name: string; download_url: string }>;
  const refs = entries
    .map((entry) => {
      const parts = entry.name.match(HISTORY_SNAPSHOT_PATTERN);
      if (!parts) {
        return null;
      }
      const [, year, month, day, hour, minute, second] = parts;
      return {
        url: entry.download_url,
        timestamp: `${year}-${month}-${day}T${hour}:${minute}:${second}Z`,
      };
    })
    .filter((ref): ref is { url: string; timestamp: string } => ref !== null)
    .sort((left, right) => left.timestamp.localeCompare(right.timestamp))
    .slice(-limit);

  return Promise.all(
    refs.map(async (ref) => {
      const snapshotResponse = await fetch(ref.url);
      if (!snapshotResponse.ok) {
        throw new Error(`Failed to load snapshot: ${snapshotResponse.status} ${snapshotResponse.statusText}`);
      }
      const data = (await snapshotResponse.json()) as RawPricingData;
      return { timestamp: ref.timestamp, models: data.models };
    }),
  );
}

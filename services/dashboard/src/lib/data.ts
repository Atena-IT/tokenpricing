import { deriveModelName, formatProvider } from "./utils";
import { loadPricingDataFromSqlite } from "./sqlite-db";

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

/** Fetch pricing data from the JSON source (always available, ~2.9 MB). */
export function loadPricingDataJson() {
  return fetchJson<RawPricingData>("current/prices.json");
}

/**
 * Load pricing data, preferring the SQLite DB when available.
 *
 * Strategy:
 *   1. Attempt to open prices.db via sql.js-httpvfs and query all models.
 *   2. On ANY error (DB unreachable, worker fails, schema version mismatch,
 *      VITE_SQLITE_ENABLED=false), silently fall back to the JSON path.
 *
 * The fallback is mandatory and airtight — the caller always gets data.
 */
export async function loadPricingData(): Promise<RawPricingData> {
  try {
    return await loadPricingDataFromSqlite();
  } catch {
    // SQLite path unavailable or disabled — use the JSON fallback.
    return loadPricingDataJson();
  }
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
 * Compact per-model price time-series produced by the sync service.
 * Fetched as a single file instead of up to 12 full ~2.8 MB snapshots.
 */
interface CompactPricePoint {
  /** ISO-8601 snapshot timestamp. */
  t: string;
  /** Input price per million tokens (USD). */
  in: number | null;
  /** Output price per million tokens (USD). */
  out: number | null;
  /** Cache-read price per million tokens (USD), or null. */
  cr: number | null;
  /** Cache-creation price per million tokens (USD), or null. */
  cc: number | null;
}

interface CompactPriceHistory {
  generated_at: string;
  models: Record<string, CompactPricePoint[]>;
}

/**
 * Convert the compact history artifact into the `HistorySnapshot[]` shape that
 * the history chart already knows how to render.  Only the four pricing fields
 * present in the compact format are populated; all other `RawModelInfo` fields
 * are set to safe defaults because the chart only reads `pricing`.
 */
function compactHistoryToSnapshots(
  compact: CompactPriceHistory,
  limit: number,
): HistorySnapshot[] {
  // Collect all distinct timestamps across all models, sorted ascending.
  const timestampSet = new Set<string>();
  for (const points of Object.values(compact.models)) {
    for (const point of points) {
      timestampSet.add(point.t);
    }
  }
  const timestamps = [...timestampSet].sort().slice(-limit);

  return timestamps.map((ts) => {
    const models: Record<string, RawModelInfo> = {};
    for (const [modelId, points] of Object.entries(compact.models)) {
      const point = points.find((p) => p.t === ts);
      if (!point) {
        continue;
      }
      // Populate only the fields the history chart reads (pricing.*).
      models[modelId] = {
        provider: modelId.split("/")[0] ?? "",
        model_id: modelId,
        display_name: modelId,
        pricing: {
          input_per_million: point.in ?? 0,
          output_per_million: point.out ?? 0,
          cache_read_per_million: point.cr,
          cache_creation_per_million: point.cc,
          currency: "USD",
        },
        context_window: 0,
        max_output_tokens: 0,
        model_type: "text",
        supports_vision: false,
        supports_function_calling: false,
        supports_streaming: false,
        category: "standard",
      };
    }
    return { timestamp: ts, models };
  });
}

/**
 * Primary path: fetch the single compact history artifact
 * (`current/price-history.json`) and convert it to `HistorySnapshot[]`.
 *
 * Falls back to the legacy multi-snapshot method if the compact file is
 * missing (404) or cannot be parsed, so nothing breaks during rollout.
 */
export async function loadHistorySnapshots(limit = 12): Promise<HistorySnapshot[]> {
  try {
    const compact = await fetchJson<CompactPriceHistory>("current/price-history.json");
    return compactHistoryToSnapshots(compact, limit);
  } catch {
    // Compact file not yet available — fall back to the legacy snapshot listing.
    return loadHistorySnapshotsLegacy(limit);
  }
}

/**
 * Legacy fallback: lists `database/history/` via the GitHub contents API and
 * fetches up to `limit` full snapshots (~2.8 MB each).  Only called when the
 * compact `price-history.json` is unavailable.
 */
async function loadHistorySnapshotsLegacy(limit = 12): Promise<HistorySnapshot[]> {
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

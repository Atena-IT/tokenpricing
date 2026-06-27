/**
 * SQLite read path for the pricing database.
 *
 * Uses sql.js-httpvfs to open prices.db over HTTP (whole-file download with
 * in-browser query execution via sql.js).  If the DB is unreachable, range
 * requests fail, the worker errors, or `PRAGMA user_version` is not 1, this
 * module throws so the caller can silently fall back to the JSON path.
 *
 * Feature flag: set VITE_SQLITE_ENABLED=false to disable the SQLite path
 * entirely (JSON fallback is used immediately).  Default is enabled.
 */

import { createDbWorker, type WorkerHttpvfs } from "sql.js-httpvfs";
import type { RawModelInfo, RawPricingData } from "./data";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const SQLITE_ENABLED =
  (import.meta.env.VITE_SQLITE_ENABLED as string | undefined)?.trim().toLowerCase() !== "false";

/** The DB URL comes from an explicit env var, or defaults to the full
 *  database published on the rolling `database-latest` GitHub Release. The
 *  dashboard needs the full DB (it includes `price_history` for the history
 *  charts); the slim `prices-current.db` is for SDK consumers.
 *
 *  Note: browsers may be unable to fetch a release asset directly due to CORS
 *  until the DB is served from GitHub Pages. That failure is caught upstream
 *  and the app falls back to the JSON path, so there is no user-visible
 *  regression in the meantime. */
function resolvePricesDbUrl(): string {
  const explicit = (import.meta.env.VITE_PRICES_DB_URL as string | undefined)?.trim();
  if (explicit) {
    return explicit;
  }
  return "https://github.com/Atena-IT/tokenpricing/releases/download/database-latest/prices.db";
}

/**
 * Resolve the base URL for static assets (worker JS, WASM).  In dev Vite
 * serves them from /, in the GitHub Pages build from /tokenpricing/.
 */
function assetBaseUrl(): string {
  return import.meta.env.BASE_URL ?? "/";
}

// ---------------------------------------------------------------------------
// Singleton worker
// ---------------------------------------------------------------------------

let workerPromise: Promise<WorkerHttpvfs> | null = null;

function getWorker(): Promise<WorkerHttpvfs> {
  if (!workerPromise) {
    const base = assetBaseUrl().replace(/\/+$/, "");
    const workerUrl = `${base}/sqlite.worker.js`;
    const wasmUrl = `${base}/sql-wasm.wasm`;
    const dbUrl = resolvePricesDbUrl();

    workerPromise = createDbWorker(
      [
        {
          from: "inline",
          config: {
            serverMode: "full",
            url: dbUrl,
            requestChunkSize: 4096,
          },
        },
      ],
      workerUrl,
      wasmUrl,
      // Limit to 128 MB to avoid runaway reads — the DB is < 5 MB.
      128 * 1024 * 1024,
    ).catch((err: unknown) => {
      // Reset so the next call retries.
      workerPromise = null;
      throw err;
    });
  }
  return workerPromise;
}

// ---------------------------------------------------------------------------
// Schema version guard
// ---------------------------------------------------------------------------

async function assertSchemaVersion(worker: WorkerHttpvfs): Promise<void> {
  const rows = (await worker.db.query("PRAGMA user_version")) as Array<{ user_version: number }>;
  const version = rows[0]?.user_version;
  if (version !== 1) {
    throw new Error(
      `prices.db has schema version ${version}, expected 1 — falling back to JSON`,
    );
  }
}

// ---------------------------------------------------------------------------
// Row mapping
// ---------------------------------------------------------------------------

interface DbModelRow {
  model_id: string;
  provider: string;
  display_name: string;
  input_per_million: number | null;
  output_per_million: number | null;
  cache_read_per_million: number | null;
  cache_creation_per_million: number | null;
  currency: string;
  context_window: number | null;
  max_output_tokens: number | null;
  model_type: string | null;
  category: string | null;
  supports_vision: number | null;
  supports_function_calling: number | null;
  supports_streaming: number | null;
}

function dbRowToRawModelInfo(row: DbModelRow): RawModelInfo {
  return {
    model_id: row.model_id,
    provider: row.provider,
    display_name: row.display_name,
    pricing: {
      input_per_million: row.input_per_million ?? 0,
      output_per_million: row.output_per_million ?? 0,
      cache_read_per_million: row.cache_read_per_million ?? null,
      cache_creation_per_million: row.cache_creation_per_million ?? null,
      currency: row.currency ?? "USD",
    },
    context_window: row.context_window ?? 0,
    max_output_tokens: row.max_output_tokens ?? 0,
    model_type: row.model_type ?? "text",
    supports_vision: row.supports_vision === 1,
    supports_function_calling: row.supports_function_calling === 1,
    supports_streaming: row.supports_streaming === 1,
    category: row.category ?? "",
  };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Load all models from the SQLite DB.  Returns a RawPricingData-shaped object
 * so it can be used as a drop-in replacement for the JSON fetch.
 *
 * Throws if:
 * - VITE_SQLITE_ENABLED=false
 * - The worker/wasm fails to load
 * - The DB is unreachable (fetch error)
 * - PRAGMA user_version != 1
 */
export async function loadPricingDataFromSqlite(): Promise<RawPricingData> {
  if (!SQLITE_ENABLED) {
    throw new Error("SQLite path is disabled via VITE_SQLITE_ENABLED=false");
  }

  const worker = await getWorker();

  await assertSchemaVersion(worker);

  // Read generated_at from meta table (best-effort; fall back to empty string).
  let generated_at = "";
  try {
    const metaRows = (await worker.db.query(
      "SELECT generated_at FROM meta LIMIT 1",
    )) as Array<{ generated_at: string }>;
    generated_at = metaRows[0]?.generated_at ?? "";
  } catch {
    // meta table missing in this build — non-fatal
  }

  const rows = (await worker.db.query(
    `SELECT model_id, provider, display_name,
            input_per_million, output_per_million,
            cache_read_per_million, cache_creation_per_million,
            currency, context_window, max_output_tokens,
            model_type, category,
            supports_vision, supports_function_calling, supports_streaming
     FROM models`,
  )) as DbModelRow[];

  const models: Record<string, RawModelInfo> = {};
  for (const row of rows) {
    models[row.model_id] = dbRowToRawModelInfo(row);
  }

  return { generated_at, models };
}

/**
 * Check if the SQLite path appears to be usable without loading all data.
 * Resolves true when the worker opens and schema version is correct.
 * Used for diagnostics / health checks.
 */
export async function isSqliteAvailable(): Promise<boolean> {
  if (!SQLITE_ENABLED) return false;
  try {
    const worker = await getWorker();
    await assertSchemaVersion(worker);
    return true;
  } catch {
    return false;
  }
}

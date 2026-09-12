/**
 * Optional SQLite read backend for tokenpricing (Node.js only).
 *
 * Downloads `prices-current.db` (the slim database, without `price_history`)
 * from a configurable URL (default: rolling GitHub Release at `database-latest`),
 * caches it on disk with a 6-hour freshness TTL, and returns a `RawPricingData`
 * object identical in shape to what the JSON path produces.
 *
 * The SDK never queries `price_history`, so the slim database is a drop-in
 * replacement for the full `prices.db`. Using it results in a materially
 * smaller download on first use. To switch to the full database set
 * `TOKENPRICING_DB_URL` to the `prices.db` release URL.
 *
 * Activation
 * ----------
 * Set `TOKENPRICING_USE_SQLITE=1` (or `true` / `yes`, case-insensitive) before
 * importing. When OFF (default) the existing HTTP-JSON path is used and this
 * module is never invoked by the SDK.
 *
 * Fallback contract
 * -----------------
 * Every public entry-point in this module throws `SQLiteBackendError` on ANY
 * failure (not a Node.js environment, download error, schema mismatch, sqlite
 * error, missing FTS table …). The caller (`pricing.ts`) catches that base
 * class and falls back to JSON transparently.
 *
 * URL override
 * ------------
 * Set `TOKENPRICING_DB_URL` to use a different download URL.
 *
 * Cache directory override
 * ------------------------
 * Set `TOKENPRICING_DB_CACHE_DIR` to override the default OS temp-dir-based
 * cache path (`<tmpdir>/tokenpricing/prices-current.db`).
 */

import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

import type {
  RawMetadataInfo,
  RawModelInfo,
  RawPricingData,
  RawProviderInfo,
  RawSourceInfo,
} from "./modeling.js";

// ---------------------------------------------------------------------------
// Configuration constants
// ---------------------------------------------------------------------------

const DEFAULT_DB_DOWNLOAD_URL =
  "https://github.com/Atena-IT/tokenpricing/releases/download/database-latest/prices-current.db";

/** 6 hours — mirrors the JSON cache TTL */
const DB_CACHE_TTL_MS = 6 * 60 * 60 * 1000;

/** Read the download URL at call time so env-var overrides set after import work. */
function getDbDownloadUrl(): string {
  return (
    (typeof process !== "undefined" && process.env?.TOKENPRICING_DB_URL) ||
    DEFAULT_DB_DOWNLOAD_URL
  );
}

const EXPECTED_USER_VERSION = 1;

const DOWNLOAD_TIMEOUT_MS = 30_000;

// ---------------------------------------------------------------------------
// Public exception (callers catch this to trigger JSON fallback)
// ---------------------------------------------------------------------------

export class SQLiteBackendError extends Error {
  constructor(message: string, cause?: unknown) {
    super(message, { cause });
    this.name = "SQLiteBackendError";
  }
}

// ---------------------------------------------------------------------------
// Node.js guard
// ---------------------------------------------------------------------------

function isNode(): boolean {
  return (
    typeof process !== "undefined" &&
    typeof process.versions !== "undefined" &&
    typeof process.versions.node !== "undefined"
  );
}

// ---------------------------------------------------------------------------
// Cache directory + path helpers
// ---------------------------------------------------------------------------

function cacheDir(): string {
  if (
    typeof process !== "undefined" &&
    process.env?.TOKENPRICING_DB_CACHE_DIR
  ) {
    return process.env.TOKENPRICING_DB_CACHE_DIR;
  }
  return path.join(os.tmpdir(), "tokenpricing");
}

function dbPath(): string {
  return path.join(cacheDir(), "prices-current.db");
}

// ---------------------------------------------------------------------------
// DB freshness + download
// ---------------------------------------------------------------------------

function isFresh(filePath: string): boolean {
  try {
    const stat = fs.statSync(filePath);
    return Date.now() - stat.mtimeMs < DB_CACHE_TTL_MS;
  } catch {
    return false;
  }
}

async function downloadDb(dest: string): Promise<void> {
  const dir = path.dirname(dest);
  fs.mkdirSync(dir, { recursive: true });

  const url = getDbDownloadUrl();
  let response: Response;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), DOWNLOAD_TIMEOUT_MS);
    try {
      response = await fetch(url, {
        signal: controller.signal,
        // Follow redirects by default in modern fetch implementations
        redirect: "follow",
      });
    } finally {
      clearTimeout(timer);
    }
  } catch (err) {
    throw new SQLiteBackendError(
      `Failed to download prices-current.db: ${err}`,
      err,
    );
  }

  if (!response.ok) {
    throw new SQLiteBackendError(
      `Failed to download prices-current.db: HTTP ${response.status} ${response.statusText}`,
    );
  }

  const buffer = await response.arrayBuffer();

  // Write to a temp file in the same dir, then rename atomically
  const tmpPath = `${dest}.tmp.${process.pid}`;
  try {
    fs.writeFileSync(tmpPath, Buffer.from(buffer));
    fs.renameSync(tmpPath, dest);
  } catch (err) {
    try {
      fs.unlinkSync(tmpPath);
    } catch {
      // ignore cleanup errors
    }
    throw new SQLiteBackendError(
      `Failed to write prices-current.db to cache: ${err}`,
      err,
    );
  }
}

async function ensureDb(): Promise<string> {
  const p = dbPath();
  if (!isFresh(p)) {
    await downloadDb(p);
  }
  return p;
}

// ---------------------------------------------------------------------------
// better-sqlite3 dynamic import (avoids bundling in browser paths)
// ---------------------------------------------------------------------------

// better-sqlite3 uses `export =` so its module type is DatabaseConstructor.
// We alias it to make intent clear.
type BetterSqlite3Ctor = typeof import("better-sqlite3");
type Database = import("better-sqlite3").Database;
type Statement = import("better-sqlite3").Statement;

let _ctor: BetterSqlite3Ctor | null = null;

async function getDbConstructor(): Promise<BetterSqlite3Ctor> {
  if (_ctor) return _ctor;
  try {
    // Dynamic import keeps better-sqlite3 out of bundled browser paths.
    // better-sqlite3 ships a CJS package; when loaded via ESM dynamic import
    // the constructor lands on `.default`.
    const mod = (await import("better-sqlite3")) as unknown as {
      default: BetterSqlite3Ctor;
    };
    _ctor = mod.default;
    return _ctor;
  } catch (err) {
    throw new SQLiteBackendError(
      "better-sqlite3 is not installed. Install it with: npm install better-sqlite3",
      err,
    );
  }
}

// ---------------------------------------------------------------------------
// Read-only connection helpers
// ---------------------------------------------------------------------------

interface OpenDbResult {
  db: Database;
  close: () => void;
}

async function openDb(filePath: string): Promise<OpenDbResult> {
  const Ctor = await getDbConstructor();
  let db: Database;
  try {
    // `Ctor` is `BetterSqlite3Ctor` which is the `DatabaseConstructor` and
    // supports `new Ctor(...)` per its interface definition.
    db = new (
      Ctor as unknown as new (
        f: string,
        o: Record<string, unknown>,
      ) => Database
    )(filePath, { readonly: true });
  } catch (err) {
    throw new SQLiteBackendError(`Cannot open prices-current.db: ${err}`, err);
  }

  // Validate schema version
  const versionRow = db.prepare("PRAGMA user_version").get() as {
    user_version: number;
  };
  const version = versionRow.user_version;
  if (version !== EXPECTED_USER_VERSION) {
    db.close();
    throw new SQLiteBackendError(
      `prices-current.db has schema version ${version}, expected ${EXPECTED_USER_VERSION}`,
    );
  }

  // Verify FTS table exists
  const ftsRow = db
    .prepare(
      "SELECT name FROM sqlite_master WHERE type='table' AND name='models_fts'",
    )
    .get() as { name: string } | undefined;
  if (!ftsRow) {
    db.close();
    throw new SQLiteBackendError(
      "prices-current.db is missing the models_fts FTS table",
    );
  }

  return { db, close: () => db.close() };
}

// ---------------------------------------------------------------------------
// Row → RawPricingData helpers
// ---------------------------------------------------------------------------

interface ModelRow {
  model_id: string;
  provider: string;
  display_name: string;
  input_per_million: number | null;
  output_per_million: number | null;
  cache_read_per_million: number | null;
  cache_creation_per_million: number | null;
  currency: string | null;
  context_window: number | null;
  max_output_tokens: number | null;
  model_type: string | null;
  category: string | null;
  supports_vision: number | null;
  supports_function_calling: number | null;
  supports_streaming: number | null;
}

interface ProviderRow {
  provider: string;
  name: string | null;
  website: string | null;
  pricing_page: string | null;
  affiliate_link: string | null;
}

interface SourceRow {
  model_id: string;
  source: string;
  price_input: number | null;
  price_output: number | null;
  price_cache_read: number | null;
  price_cache_creation: number | null;
  last_updated: string | null;
}

interface MetaRow {
  generated_at: string | null;
  total_models: number | null;
  schema_version: number | null;
}

function rowToRawModelInfo(
  row: ModelRow,
  sources: Record<string, RawSourceInfo>,
): RawModelInfo {
  return {
    provider: row.provider,
    model_id: row.model_id,
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
    supports_vision: Boolean(row.supports_vision),
    supports_function_calling: Boolean(row.supports_function_calling),
    supports_streaming: Boolean(row.supports_streaming),
    category: row.category ?? "standard",
    sources,
  };
}

function fetchSourcesForModels(
  db: Database,
  modelIds: string[],
): Record<string, Record<string, RawSourceInfo>> {
  if (modelIds.length === 0) return {};

  const placeholders = modelIds.map(() => "?").join(",");
  const stmt: Statement = db.prepare(
    `SELECT model_id, source, price_input, price_output,
     price_cache_read, price_cache_creation, last_updated
     FROM model_sources WHERE model_id IN (${placeholders})`,
  );
  const rows = stmt.all(...modelIds) as SourceRow[];

  const result: Record<string, Record<string, RawSourceInfo>> = {};
  for (const mid of modelIds) {
    result[mid] = {};
  }
  for (const r of rows) {
    result[r.model_id][r.source] = {
      price_input: r.price_input ?? 0,
      price_output: r.price_output ?? 0,
      price_cache_read: r.price_cache_read ?? null,
      price_cache_creation: r.price_cache_creation ?? null,
      last_updated: r.last_updated ?? new Date().toISOString(),
    };
  }
  return result;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Load the full pricing dataset from SQLite and return a `RawPricingData`
 * object — identical in shape to what the JSON path produces.
 *
 * This is the main entry-point used by `pricing.ts` when
 * `TOKENPRICING_USE_SQLITE` is set.
 *
 * @throws {SQLiteBackendError} on any failure — caller should fall back to JSON.
 */
export async function getAllPricingData(): Promise<RawPricingData> {
  if (!isNode()) {
    throw new SQLiteBackendError(
      "SQLite backend is only supported in Node.js environments",
    );
  }

  try {
    const filePath = await ensureDb();
    const { db, close } = await openDb(filePath);

    try {
      // --- meta ---
      const meta = db
        .prepare(
          "SELECT generated_at, total_models, schema_version FROM meta LIMIT 1",
        )
        .get() as MetaRow | undefined;

      const generatedAt = meta?.generated_at ?? new Date().toISOString();
      const totalModels = meta?.total_models ?? 0;

      // --- providers ---
      const providerRows = db
        .prepare(
          "SELECT provider, name, website, pricing_page, affiliate_link FROM providers",
        )
        .all() as ProviderRow[];

      const providers: Record<string, RawProviderInfo> = {};
      for (const r of providerRows) {
        providers[r.provider] = {
          name: r.name ?? r.provider,
          website: r.website ?? "",
          pricing_page: r.pricing_page ?? "",
          affiliate_link: r.affiliate_link ?? null,
        };
      }

      // --- models ---
      const modelRows = db.prepare("SELECT * FROM models").all() as ModelRow[];
      const modelIds = modelRows.map((r) => r.model_id);
      const sourcesMap = fetchSourcesForModels(db, modelIds);

      const models: Record<string, RawModelInfo> = {};
      for (const row of modelRows) {
        models[row.model_id] = rowToRawModelInfo(
          row,
          sourcesMap[row.model_id] ?? {},
        );
      }

      // --- metadata ---
      const metadata: RawMetadataInfo = {
        total_models: totalModels || modelIds.length,
        sources: ["openrouter", "litellm"],
        last_scrape: generatedAt,
        categories: {},
      };

      return {
        generated_at: generatedAt,
        models,
        providers,
        metadata,
      };
    } finally {
      close();
    }
  } catch (err) {
    if (err instanceof SQLiteBackendError) throw err;
    throw new SQLiteBackendError(
      `Failed to load pricing data from SQLite: ${err}`,
      err,
    );
  }
}

// ---------------------------------------------------------------------------
// Env-var helpers (exported for use by pricing.ts and tests)
// ---------------------------------------------------------------------------

/**
 * Return true when the caller has opted in via `TOKENPRICING_USE_SQLITE`.
 *
 * Truthy values: `"1"`, `"true"`, `"yes"` (case-insensitive).
 * Everything else — including unset / empty / `"0"` / `"false"` / `"no"` — is falsy.
 */
export function isSqliteEnabled(): boolean {
  if (typeof process === "undefined") return false;
  const val = (process.env?.TOKENPRICING_USE_SQLITE ?? "").trim().toLowerCase();
  return val === "1" || val === "true" || val === "yes";
}

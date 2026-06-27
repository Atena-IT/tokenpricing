/**
 * Tests for the SQLite backend module.
 *
 * These tests use a pre-built fixture database at tests/fixtures/prices-current.db
 * and mock `TOKENPRICING_DB_CACHE_DIR` to point at the fixtures directory so
 * no network download is needed.
 */

import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  getAllPricingData,
  isSqliteEnabled,
  SQLiteBackendError,
} from "../src/sqlite-backend.js";

// Path to the pre-built fixture database
const FIXTURES_DIR = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  "fixtures",
);
// FIXTURES_DIR contains prices-current.db; the path is used indirectly via
// TOKENPRICING_DB_CACHE_DIR which the module resolves to <dir>/prices-current.db

// ---------------------------------------------------------------------------
// isSqliteEnabled
// ---------------------------------------------------------------------------

describe("isSqliteEnabled", () => {
  const originalEnv = process.env.TOKENPRICING_USE_SQLITE;

  afterEach(() => {
    if (originalEnv === undefined) {
      delete process.env.TOKENPRICING_USE_SQLITE;
    } else {
      process.env.TOKENPRICING_USE_SQLITE = originalEnv;
    }
  });

  it("returns false when env var is unset", () => {
    delete process.env.TOKENPRICING_USE_SQLITE;
    expect(isSqliteEnabled()).toBe(false);
  });

  it.each([
    "1",
    "true",
    "TRUE",
    "True",
    "yes",
    "YES",
  ])('returns true for truthy value "%s"', (val) => {
    process.env.TOKENPRICING_USE_SQLITE = val;
    expect(isSqliteEnabled()).toBe(true);
  });

  it.each([
    "0",
    "false",
    "no",
    "",
    "off",
  ])('returns false for falsy value "%s"', (val) => {
    process.env.TOKENPRICING_USE_SQLITE = val;
    expect(isSqliteEnabled()).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// getAllPricingData — happy path using fixture DB
// ---------------------------------------------------------------------------

describe("getAllPricingData", () => {
  let originalCacheDir: string | undefined;
  let originalDbUrl: string | undefined;

  beforeEach(() => {
    originalCacheDir = process.env.TOKENPRICING_DB_CACHE_DIR;
    originalDbUrl = process.env.TOKENPRICING_DB_URL;
    // Point the cache dir at the fixtures dir so the module uses the
    // pre-built DB without attempting a network download.
    process.env.TOKENPRICING_DB_CACHE_DIR = FIXTURES_DIR;
    // Set a bogus URL — the file is already fresh so no download occurs.
    process.env.TOKENPRICING_DB_URL =
      "https://example.invalid/prices-current.db";
  });

  afterEach(() => {
    if (originalCacheDir === undefined) {
      delete process.env.TOKENPRICING_DB_CACHE_DIR;
    } else {
      process.env.TOKENPRICING_DB_CACHE_DIR = originalCacheDir;
    }
    if (originalDbUrl === undefined) {
      delete process.env.TOKENPRICING_DB_URL;
    } else {
      process.env.TOKENPRICING_DB_URL = originalDbUrl;
    }
  });

  it("returns RawPricingData with the correct top-level shape", async () => {
    const data = await getAllPricingData();
    expect(data).toHaveProperty("generated_at");
    expect(data).toHaveProperty("models");
    expect(data).toHaveProperty("providers");
    expect(data).toHaveProperty("metadata");
    expect(typeof data.generated_at).toBe("string");
    expect(typeof data.models).toBe("object");
    expect(typeof data.providers).toBe("object");
  });

  it("populates fixture models correctly", async () => {
    const data = await getAllPricingData();

    // Model from fixture
    const gpt4 = data.models["openai/gpt-4"];
    expect(gpt4).toBeDefined();
    expect(gpt4.display_name).toBe("GPT-4");
    expect(gpt4.provider).toBe("openai");
    expect(gpt4.pricing.input_per_million).toBe(30);
    expect(gpt4.pricing.output_per_million).toBe(60);
    expect(gpt4.pricing.cache_read_per_million).toBe(15);
    expect(gpt4.pricing.cache_creation_per_million).toBe(45);
    expect(gpt4.pricing.currency).toBe("USD");
    expect(gpt4.context_window).toBe(8192);
    expect(gpt4.max_output_tokens).toBe(4096);
    expect(gpt4.model_type).toBe("text");
    expect(gpt4.category).toBe("flagship");
    expect(gpt4.supports_vision).toBe(false);
    expect(gpt4.supports_function_calling).toBe(true);
    expect(gpt4.supports_streaming).toBe(true);
  });

  it("handles null optional pricing fields correctly", async () => {
    const data = await getAllPricingData();
    const claude = data.models["anthropic/claude-3-opus"];
    expect(claude).toBeDefined();
    expect(claude.pricing.cache_read_per_million).toBeNull();
    expect(claude.pricing.cache_creation_per_million).toBeNull();
  });

  it("populates providers from the fixture", async () => {
    const data = await getAllPricingData();
    expect(data.providers.openai).toBeDefined();
    expect(data.providers.openai.name).toBe("OpenAI");
    expect(data.providers.openai.website).toBe("https://openai.com");
    expect(data.providers.anthropic).toBeDefined();
  });

  it("populates model sources", async () => {
    const data = await getAllPricingData();
    const gpt4 = data.models["openai/gpt-4"];
    expect(gpt4.sources).toBeDefined();
    expect(gpt4.sources.openrouter).toBeDefined();
    expect(gpt4.sources.openrouter.price_input).toBe(30);
    expect(gpt4.sources.openrouter.price_output).toBe(60);
  });

  it("populates metadata", async () => {
    const data = await getAllPricingData();
    expect(data.metadata.total_models).toBeGreaterThan(0);
    expect(Array.isArray(data.metadata.sources)).toBe(true);
    expect(typeof data.metadata.last_scrape).toBe("string");
  });

  it("metadata generated_at matches fixture value", async () => {
    const data = await getAllPricingData();
    expect(data.generated_at).toBe("2024-01-01T00:00:00Z");
  });
});

// ---------------------------------------------------------------------------
// getAllPricingData — error / fallback paths
// ---------------------------------------------------------------------------

describe("getAllPricingData error paths", () => {
  let originalCacheDir: string | undefined;
  let tmpDir: string;

  beforeEach(() => {
    originalCacheDir = process.env.TOKENPRICING_DB_CACHE_DIR;
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "tokenpricing-test-"));
  });

  afterEach(() => {
    if (originalCacheDir === undefined) {
      delete process.env.TOKENPRICING_DB_CACHE_DIR;
    } else {
      process.env.TOKENPRICING_DB_CACHE_DIR = originalCacheDir;
    }
    // Clean up temp dir
    try {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    } catch {
      // ignore
    }
  });

  it("throws SQLiteBackendError when DB is absent and download returns a 404", async () => {
    // Point to an empty tmp dir; mock fetch to return 404
    process.env.TOKENPRICING_DB_CACHE_DIR = tmpDir;
    process.env.TOKENPRICING_DB_URL = "https://example.test/prices-current.db";

    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
    });

    try {
      await expect(getAllPricingData()).rejects.toBeInstanceOf(
        SQLiteBackendError,
      );
    } finally {
      globalThis.fetch = originalFetch;
      delete process.env.TOKENPRICING_DB_URL;
    }
  });

  it("throws SQLiteBackendError when DB has wrong schema version", async () => {
    // Create a DB with user_version = 99
    const badDbPath = path.join(tmpDir, "prices-current.db");
    const Database = (await import("better-sqlite3")).default;
    const db = new Database(badDbPath);
    db.exec("PRAGMA user_version = 99; CREATE TABLE meta (x INTEGER);");
    db.close();

    // Touch the file so it appears fresh
    const now = Date.now() / 1000;
    fs.utimesSync(badDbPath, now, now);

    process.env.TOKENPRICING_DB_CACHE_DIR = tmpDir;

    await expect(getAllPricingData()).rejects.toBeInstanceOf(
      SQLiteBackendError,
    );
    await expect(getAllPricingData()).rejects.toThrow(/schema version/);
  });

  it("throws SQLiteBackendError when models_fts table is missing", async () => {
    const badDbPath = path.join(tmpDir, "prices-current.db");
    const Database = (await import("better-sqlite3")).default;
    const db = new Database(badDbPath);
    db.exec(`
      PRAGMA user_version = 1;
      CREATE TABLE meta (generated_at TEXT, total_models INTEGER, schema_version INTEGER);
      CREATE TABLE models (model_id TEXT PRIMARY KEY, provider TEXT NOT NULL,
        display_name TEXT NOT NULL, input_per_million REAL, output_per_million REAL,
        cache_read_per_million REAL, cache_creation_per_million REAL,
        currency TEXT NOT NULL DEFAULT 'USD', context_window INTEGER,
        max_output_tokens INTEGER, model_type TEXT, category TEXT,
        supports_vision INTEGER, supports_function_calling INTEGER, supports_streaming INTEGER);
      CREATE TABLE providers (provider TEXT PRIMARY KEY, name TEXT, website TEXT, pricing_page TEXT, affiliate_link TEXT);
      CREATE TABLE model_sources (model_id TEXT, source TEXT, price_input REAL, price_output REAL, price_cache_read REAL, price_cache_creation REAL, last_updated TEXT, PRIMARY KEY (model_id, source));
    `);
    db.close();

    const now = Date.now() / 1000;
    fs.utimesSync(badDbPath, now, now);

    process.env.TOKENPRICING_DB_CACHE_DIR = tmpDir;

    await expect(getAllPricingData()).rejects.toBeInstanceOf(
      SQLiteBackendError,
    );
    await expect(getAllPricingData()).rejects.toThrow(/models_fts/);
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { computeCost, getPricing } from "../src/core.js";
import { clearRatesCache } from "../src/currency.js";
import { clearPricingCache } from "../src/pricing.js";

// Mock global fetch
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

const SAMPLE_PRICING_DATA = {
  generated_at: "2024-01-01T00:00:00Z",
  models: {
    "openai/gpt-4": {
      provider: "openai",
      model_id: "openai/gpt-4",
      display_name: "GPT-4",
      pricing: {
        input_per_million: 30,
        output_per_million: 60,
        currency: "USD",
      },
      context_window: 8192,
      max_output_tokens: 4096,
      model_type: "chat",
      supports_vision: false,
      supports_function_calling: true,
      supports_streaming: true,
      category: "flagship",
      sources: {},
      affiliate_links: {},
    },
    "anthropic/claude-3-opus": {
      provider: "anthropic",
      model_id: "anthropic/claude-3-opus",
      display_name: "Claude 3 Opus",
      pricing: {
        input_per_million: 15,
        output_per_million: 75,
        currency: "USD",
      },
      context_window: 200000,
      max_output_tokens: 4096,
      model_type: "chat",
      supports_vision: true,
      supports_function_calling: true,
      supports_streaming: true,
      category: "flagship",
      sources: {},
      affiliate_links: {},
    },
  },
  providers: {
    openai: {
      name: "OpenAI",
      website: "https://openai.com",
      pricing_page: "https://openai.com/pricing",
      affiliate_link: "",
    },
    anthropic: {
      name: "Anthropic",
      website: "https://anthropic.com",
      pricing_page: "https://anthropic.com/pricing",
      affiliate_link: "",
    },
  },
  metadata: {
    total_models: 2,
    sources: ["openai", "anthropic"],
    last_scrape: "2024-01-01T00:00:00Z",
    categories: { flagship: 2 },
  },
};

const SAMPLE_FX_DATA = {
  usd: {
    eur: 0.92,
    gbp: 0.79,
  },
};

function mockPricingFetch() {
  mockFetch.mockImplementation((url: string) => {
    if (url.includes("LLMTracker")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(SAMPLE_PRICING_DATA),
      });
    }
    if (url.includes("currency-api")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(SAMPLE_FX_DATA),
      });
    }
    return Promise.resolve({ ok: false, status: 404, statusText: "Not Found" });
  });
}

describe("getPricing", () => {
  afterEach(() => {
    clearPricingCache();
    clearRatesCache();
    mockFetch.mockReset();
  });

  it("should return pricing in USD", async () => {
    mockPricingFetch();

    const pricing = await getPricing("openai/gpt-4");
    expect(pricing.inputPerMillion).toBe(30);
    expect(pricing.outputPerMillion).toBe(60);
    expect(pricing.currency).toBe("USD");
  });

  it("should convert pricing to another currency", async () => {
    mockPricingFetch();

    const pricing = await getPricing("openai/gpt-4", "EUR");
    expect(pricing.inputPerMillion).toBeCloseTo(30 * 0.92);
    expect(pricing.outputPerMillion).toBeCloseTo(60 * 0.92);
    expect(pricing.currency).toBe("EUR");
  });

  it("should throw for unknown model with suggestion", async () => {
    mockPricingFetch();

    await expect(getPricing("openai/gpt4")).rejects.toThrow(/Did you mean/);
  });

  it("should throw for completely unknown model", async () => {
    mockPricingFetch();

    await expect(getPricing("zzzzz/nonexistent-model-xyz")).rejects.toThrow(
      "Model not found",
    );
  });
});

describe("computeCost", () => {
  afterEach(() => {
    clearPricingCache();
    clearRatesCache();
    mockFetch.mockReset();
  });

  it("should compute cost in USD", async () => {
    mockPricingFetch();

    const cost = await computeCost("openai/gpt-4", 1000, 500);
    // input: 1000/1M * 30 = 0.03, output: 500/1M * 60 = 0.03
    expect(cost).toBeCloseTo(0.06);
  });

  it("should compute cost in EUR", async () => {
    mockPricingFetch();

    const cost = await computeCost("openai/gpt-4", 1000, 500, "EUR");
    expect(cost).toBeCloseTo(0.06 * 0.92);
  });

  it("should return 0 for zero tokens", async () => {
    mockPricingFetch();

    const cost = await computeCost("openai/gpt-4", 0, 0);
    expect(cost).toBe(0);
  });

  it("should throw for negative token counts", async () => {
    await expect(computeCost("openai/gpt-4", -1, 0)).rejects.toThrow(
      "non-negative",
    );
  });
});

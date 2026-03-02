import { afterEach, describe, expect, it, vi } from "vitest";
import { clearPricingCache, getPricingData } from "../src/pricing.js";

// Mock global fetch
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

const SAMPLE_DATA = {
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
  },
  providers: {
    openai: {
      name: "OpenAI",
      website: "https://openai.com",
      pricing_page: "https://openai.com/pricing",
      affiliate_link: "",
    },
  },
  metadata: {
    total_models: 1,
    sources: ["openai"],
    last_scrape: "2024-01-01T00:00:00Z",
    categories: { flagship: 1 },
  },
};

describe("getPricingData", () => {
  afterEach(() => {
    clearPricingCache();
    mockFetch.mockReset();
  });

  it("should fetch and parse pricing data", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(SAMPLE_DATA),
    });

    const data = await getPricingData();
    expect(data.models["openai/gpt-4"].display_name).toBe("GPT-4");
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("should cache pricing data on subsequent calls", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(SAMPLE_DATA),
    });

    await getPricingData();
    await getPricingData();
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("should force refresh when requested", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(SAMPLE_DATA),
    });

    await getPricingData();
    await getPricingData(true);
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it("should throw on non-200 response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
    });

    await expect(getPricingData()).rejects.toThrow(
      "Failed to fetch pricing data",
    );
  });
});

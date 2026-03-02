import { describe, expect, it } from "vitest";
import { parsePricingData, toPricingInfo } from "../src/modeling.js";

describe("parsePricingData", () => {
  const validData = {
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

  it("should parse valid pricing data", () => {
    const result = parsePricingData(validData);
    expect(result.generated_at).toBe("2024-01-01T00:00:00Z");
    expect(result.models["openai/gpt-4"].display_name).toBe("GPT-4");
    expect(result.models["openai/gpt-4"].pricing.input_per_million).toBe(30);
  });

  it("should reject non-object input", () => {
    expect(() => parsePricingData(null)).toThrow("expected object");
    expect(() => parsePricingData("string")).toThrow("expected object");
    expect(() => parsePricingData(42)).toThrow("expected object");
  });

  it("should reject missing generated_at", () => {
    expect(() =>
      parsePricingData({ models: {}, providers: {}, metadata: {} }),
    ).toThrow("missing generated_at");
  });

  it("should reject missing models", () => {
    expect(() =>
      parsePricingData({ generated_at: "x", providers: {}, metadata: {} }),
    ).toThrow("missing models");
  });

  it("should reject missing providers", () => {
    expect(() =>
      parsePricingData({ generated_at: "x", models: {}, metadata: {} }),
    ).toThrow("missing providers");
  });

  it("should reject missing metadata", () => {
    expect(() =>
      parsePricingData({ generated_at: "x", models: {}, providers: {} }),
    ).toThrow("missing metadata");
  });
});

describe("toPricingInfo", () => {
  it("should convert raw pricing to public interface", () => {
    const raw = {
      input_per_million: 30,
      output_per_million: 60,
      currency: "USD",
    };
    const result = toPricingInfo(raw);

    expect(result.inputPerMillion).toBe(30);
    expect(result.outputPerMillion).toBe(60);
    expect(result.currency).toBe("USD");
  });

  it("should override currency when provided", () => {
    const raw = {
      input_per_million: 30,
      output_per_million: 60,
      currency: "USD",
    };
    const result = toPricingInfo(raw, "EUR");

    expect(result.currency).toBe("EUR");
  });
});

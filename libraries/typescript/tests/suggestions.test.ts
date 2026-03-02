import { describe, expect, it } from "vitest";
import {
  suggestCurrency,
  suggestMatch,
  suggestModel,
} from "../src/suggestions.js";

describe("suggestMatch", () => {
  it("should return null for empty choices", () => {
    expect(suggestMatch("test", [])).toBeNull();
  });

  it("should find exact case-insensitive match", () => {
    const result = suggestMatch("hello", ["Hello", "world"]);
    expect(result).not.toBeNull();
    expect(result?.match).toBe("Hello");
    expect(result?.score).toBe(100);
  });

  it("should find close fuzzy match", () => {
    const result = suggestMatch("openai/gpt4", [
      "openai/gpt-4",
      "openai/gpt-3.5",
    ]);
    expect(result).not.toBeNull();
    expect(result?.match).toBe("openai/gpt-4");
  });

  it("should return null for distant match below threshold", () => {
    const result = suggestMatch("zzzzz", [
      "openai/gpt-4",
      "anthropic/claude-3",
    ]);
    expect(result).toBeNull();
  });
});

describe("suggestModel", () => {
  const modelIds = [
    "openai/gpt-4",
    "openai/gpt-3.5-turbo",
    "anthropic/claude-3-opus",
  ];
  const displayNames: Record<string, string> = {
    "openai/gpt-4": "GPT-4",
    "openai/gpt-3.5-turbo": "GPT-3.5 Turbo",
    "anthropic/claude-3-opus": "Claude 3 Opus",
  };

  it("should return null for empty model list", () => {
    expect(suggestModel("test", [])).toBeNull();
  });

  it("should find model by ID", () => {
    const result = suggestModel("openai/gpt4", modelIds);
    expect(result).not.toBeNull();
    expect(result?.match).toBe("openai/gpt-4");
  });

  it("should find model by display name", () => {
    const result = suggestModel("Claude Opus", modelIds, displayNames);
    expect(result).not.toBeNull();
    expect(result?.match).toBe("anthropic/claude-3-opus");
  });

  it("should return null for unrecognizable query", () => {
    const result = suggestModel("zzzzz", modelIds, displayNames);
    expect(result).toBeNull();
  });
});

describe("suggestCurrency", () => {
  const codes = ["USD", "EUR", "GBP", "JPY", "CNY"];

  it("should return null for empty codes", () => {
    expect(suggestCurrency("USD", [])).toBeNull();
  });

  it("should find close currency match", () => {
    const result = suggestCurrency("ERU", codes);
    expect(result).not.toBeNull();
    expect(result?.match).toBe("EUR");
  });

  it("should handle case insensitivity", () => {
    const result = suggestCurrency("eur", codes);
    expect(result).not.toBeNull();
    expect(result?.match).toBe("EUR");
  });

  it("should return null for distant match", () => {
    const result = suggestCurrency("ZZZ", codes);
    expect(result).toBeNull();
  });
});

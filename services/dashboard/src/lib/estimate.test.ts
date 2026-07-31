import { describe, expect, it } from "vitest";

import { estimateTokens } from "./estimate";

const PROSE =
  "The quick brown fox jumps over the lazy dog. Estimating how many tokens a document " +
  "is worth is not the same thing as counting them, and the difference matters when the " +
  "answer is a price. This paragraph exists to give the heuristic a realistic sample of " +
  "ordinary English prose to work on.";

const JSON_SAMPLE = JSON.stringify(
  { model: "openai/gpt-5.2", pricing: { input_per_million: 1.25, output_per_million: 10 }, tags: ["a", "b"] },
  null,
  2,
).repeat(4);

const CJK = "私はトークンの数を推定しています。".repeat(10);

describe("estimateTokens", () => {
  it("returns zero for an empty string", () => {
    expect(estimateTokens("")).toMatchObject({ tokens: 0, low: 0, high: 0 });
  });

  it("returns zero for whitespace only", () => {
    expect(estimateTokens("   \n\t  ").tokens).toBe(0);
  });

  it("lands near the ~4 characters per token rule of thumb on English prose", () => {
    const estimate = estimateTokens(PROSE);
    expect(estimate.charsPerToken).toBeGreaterThan(3.5);
    expect(estimate.charsPerToken).toBeLessThan(4.2);
  });

  it("packs fewer characters per token on symbol-dense text than on prose", () => {
    expect(estimateTokens(JSON_SAMPLE).charsPerToken).toBeLessThan(estimateTokens(PROSE).charsPerToken);
  });

  it("counts CJK characters as far heavier than latin ones", () => {
    const latin = "a".repeat(CJK.length);
    expect(estimateTokens(CJK).tokens).toBeGreaterThan(estimateTokens(latin).tokens * 2);
  });

  it("always brackets the estimate with a non-negative range", () => {
    for (const sample of [PROSE, JSON_SAMPLE, CJK, "x"]) {
      const estimate = estimateTokens(sample);
      expect(estimate.low).toBeGreaterThanOrEqual(0);
      expect(estimate.low).toBeLessThanOrEqual(estimate.tokens);
      expect(estimate.tokens).toBeLessThanOrEqual(estimate.high);
    }
  });

  it("reports whole tokens", () => {
    const estimate = estimateTokens(PROSE);
    for (const value of [estimate.tokens, estimate.low, estimate.high]) {
      expect(Number.isInteger(value)).toBe(true);
    }
  });

  it("grows with the length of the text", () => {
    expect(estimateTokens(PROSE.repeat(3)).tokens).toBeGreaterThan(estimateTokens(PROSE).tokens);
  });

  it("never reports zero tokens for text that has content", () => {
    expect(estimateTokens("hi").tokens).toBeGreaterThanOrEqual(1);
  });

  it("names the method it used", () => {
    expect(estimateTokens(PROSE).method).toBeTruthy();
  });
});

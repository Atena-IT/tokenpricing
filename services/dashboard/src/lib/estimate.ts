/**
 * Token estimation for uploaded text.
 *
 * This module deliberately produces an *estimate*, never a count. Every
 * provider ships its own tokenizer, so a single exact number would be right
 * for one model family and wrong for all the others — which is why the SDKs in
 * this repository stay out of token counting altogether. The dashboard can
 * still help, provided it reports a range and says how it got there.
 *
 * Method: characters per token, adapted to what the text is made of.
 * - Latin prose sits close to the widely used ~4 characters per token.
 * - Dense punctuation (code, JSON, markup) fragments into shorter tokens.
 * - CJK ideographs cost roughly one token each.
 */

/** Characters per token for ordinary latin-script prose. */
const PROSE_CHARS_PER_TOKEN = 4;
/** Characters per token for fully symbol-saturated text such as minified JSON. */
const SYMBOLIC_CHARS_PER_TOKEN = 2.8;
/** CJK ideographs and kana are roughly one token per character. */
const CJK_CHARS_PER_TOKEN = 1;
/** Punctuation share at which text is treated as fully symbol-saturated. */
const SYMBOL_SATURATION = 0.3;
/** Half-width of the reported range, reflecting tokenizer-to-tokenizer variance. */
const UNCERTAINTY = 0.2;

const CJK_PATTERN = /[぀-ヿ㐀-䶿一-鿿豈-﫿가-힯]/gu;  /* to be fixed? relevant? */
const SYMBOL_PATTERN = /[^\p{L}\p{N}\s]/gu;

export interface TokenEstimate {
  /** Central estimate, in whole tokens. */
  tokens: number;
  /** Lower bound of the plausible range. */
  low: number;
  /** Upper bound of the plausible range. */
  high: number;
  /** Effective characters-per-token ratio this text worked out to. */
  charsPerToken: number;
  /** Short human-readable description of how the estimate was produced. */
  method: string;
}

const EMPTY: TokenEstimate = {
  tokens: 0,
  low: 0,
  high: 0,
  charsPerToken: 0,
  method: "no text",
};

function countMatches(text: string, pattern: RegExp): number {
  return text.match(pattern)?.length ?? 0;
}

/**
 * Estimate how many tokens a piece of text is worth.
 *
 * The returned range is not a confidence interval in any statistical sense: it
 * is an honest acknowledgement that different tokenizers disagree, and it is
 * what the UI should show instead of the central value alone.
 */
export function estimateTokens(text: string): TokenEstimate {
  if (text.trim().length === 0) {
    return EMPTY;
  }

  const totalChars = text.length;
  const cjkChars = countMatches(text, CJK_PATTERN);
  const otherChars = totalChars - cjkChars;

  // How much of the non-CJK text is punctuation, brackets, operators and the
  // like. Prose sits a few percent; source code and JSON an order higher.
  const symbolShare = otherChars > 0 ? countMatches(text, SYMBOL_PATTERN) / otherChars : 0;
  const density = Math.min(symbolShare / SYMBOL_SATURATION, 1);
  const otherCharsPerToken =
    PROSE_CHARS_PER_TOKEN + (SYMBOLIC_CHARS_PER_TOKEN - PROSE_CHARS_PER_TOKEN) * density;

  const raw = cjkChars / CJK_CHARS_PER_TOKEN + otherChars / otherCharsPerToken;
  const tokens = Math.max(1, Math.round(raw));

  return {
    tokens,
    low: Math.round(tokens * (1 - UNCERTAINTY)),
    high: Math.round(tokens * (1 + UNCERTAINTY)),
    charsPerToken: totalChars / tokens,
    method: `characters-per-token heuristic, ±${Math.round(UNCERTAINTY * 100)}%`,
  };
}

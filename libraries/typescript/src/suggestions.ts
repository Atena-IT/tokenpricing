/**
 * Fuzzy matching for helpful "Did you mean?" error messages.
 *
 * Uses fuse.js for fuzzy string matching with configurable thresholds.
 * Scores are normalized to 0–100 (100 = exact match).
 */

import Fuse from "fuse.js";

const DEFAULT_SCORE_THRESHOLD = 60;

export interface FuzzyMatch {
  query: string;
  match: string;
  score: number;
}

/**
 * Convert fuse.js score (0 = perfect, 1 = worst) to 0–100 scale.
 */
function fuseScoreTo100(fuseScore: number): number {
  return Math.round((1 - fuseScore) * 100);
}

/**
 * Generic fuzzy match against a list of choices.
 */
export function suggestMatch(
  query: string,
  choices: string[],
  threshold = DEFAULT_SCORE_THRESHOLD,
): FuzzyMatch | null {
  if (choices.length === 0) return null;

  // Check for case-insensitive exact match first
  const queryLower = query.toLowerCase();
  for (const choice of choices) {
    if (choice.toLowerCase() === queryLower) {
      return { query, match: choice, score: 100 };
    }
  }

  const fuse = new Fuse(choices, {
    includeScore: true,
    threshold: 1 - threshold / 100, // Convert our threshold to fuse threshold
  });

  const results = fuse.search(query);
  if (results.length === 0) return null;

  const best = results[0];
  const score = fuseScoreTo100(best.score ?? 1);
  if (score < threshold) return null;

  return { query, match: best.item, score };
}

/**
 * Suggest a model ID based on fuzzy match against known IDs and display names.
 */
export function suggestModel(
  query: string,
  modelIds: string[],
  displayNames?: Record<string, string>,
  threshold = DEFAULT_SCORE_THRESHOLD,
): FuzzyMatch | null {
  if (modelIds.length === 0) return null;

  // Search model IDs
  const idFuse = new Fuse(modelIds, {
    includeScore: true,
    threshold: 1 - threshold / 100,
  });
  const idResults = idFuse.search(query);

  // Search display names if provided
  let nameResult: { modelId: string; score: number } | null = null;
  if (displayNames) {
    const nameToId = new Map<string, string>();
    const names: string[] = [];
    for (const [id, name] of Object.entries(displayNames)) {
      nameToId.set(name, id);
      names.push(name);
    }
    const nameFuse = new Fuse(names, {
      includeScore: true,
      threshold: 1 - threshold / 100,
    });
    const nameResults = nameFuse.search(query);
    if (nameResults.length > 0) {
      const best = nameResults[0];
      const resolvedId = nameToId.get(best.item);
      if (resolvedId) {
        nameResult = {
          modelId: resolvedId,
          score: fuseScoreTo100(best.score ?? 1),
        };
      }
    }
  }

  const idBest =
    idResults.length > 0
      ? {
          modelId: idResults[0].item,
          score: fuseScoreTo100(idResults[0].score ?? 1),
        }
      : null;

  // Pick the better match
  if (idBest && nameResult) {
    if (idBest.score >= nameResult.score) {
      return idBest.score >= threshold
        ? { query, match: idBest.modelId, score: idBest.score }
        : null;
    }
    return nameResult.score >= threshold
      ? { query, match: nameResult.modelId, score: nameResult.score }
      : null;
  }

  if (idBest && idBest.score >= threshold) {
    return { query, match: idBest.modelId, score: idBest.score };
  }

  if (nameResult && nameResult.score >= threshold) {
    return { query, match: nameResult.modelId, score: nameResult.score };
  }

  return null;
}

/**
 * Suggest a currency code based on fuzzy match.
 */
export function suggestCurrency(
  query: string,
  currencyCodes: string[],
  threshold = DEFAULT_SCORE_THRESHOLD,
): FuzzyMatch | null {
  if (currencyCodes.length === 0) return null;

  const queryUpper = query.toUpperCase().trim();
  const upperCodes = currencyCodes.map((c) => c.toUpperCase());

  const fuse = new Fuse(upperCodes, {
    includeScore: true,
    threshold: 1 - threshold / 100,
  });
  const results = fuse.search(queryUpper);

  const COMMON_CURRENCIES = new Set([
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "CNY",
    "CAD",
    "AUD",
    "CHF",
    "INR",
  ]);

  let bestMatch: string | null = null;
  let bestScore = 0;

  for (const result of results) {
    const score = fuseScoreTo100(result.score ?? 1);
    if (score < threshold) continue;

    if (score > bestScore) {
      bestScore = score;
      bestMatch = result.item;
    } else if (
      score === bestScore &&
      COMMON_CURRENCIES.has(result.item) &&
      bestMatch &&
      !COMMON_CURRENCIES.has(bestMatch)
    ) {
      bestMatch = result.item;
    }
  }

  if (!bestMatch) return null;

  // Find original-cased code
  for (const code of currencyCodes) {
    if (code.toUpperCase() === bestMatch) {
      return { query, match: code, score: bestScore };
    }
  }

  return null;
}

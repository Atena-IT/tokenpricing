# tokenpricing dashboard

Web frontend for the canonical tokenpricing dataset: a sortable pricing explorer, side-by-side model comparison, a workload cost calculator, and the sync changelog. Content mirrors the original [LLMTracker](https://mrunreal.github.io/LLMTracker/) dashboard, rebuilt with the tokenpricing design language.

## Stack

- Vite + React 19 + TypeScript
- Tailwind CSS v4 with a shadcn-style token system (light/dark, system-aware)
- Atena Reply brand palette: burgundy `#9E4754` (primary) and petrol teal `#004048` (ink/secondary)
- Radix UI primitives (tabs, select) + a custom searchable combobox for the 3k+ model catalog
- TanStack Table for sorting, filtering, and pagination in the explorer
- Recharts for the comparison chart
- Sentient (Fontshare) for display headings, Inter Variable + JetBrains Mono Variable via Fontsource

## Data

The app fetches `database/current/prices.json` and `database/changelog/latest.json` from the canonical GitHub raw endpoint. Override the root with `VITE_CANONICAL_DATA_ROOT` (e.g. point it at a local clone during development).

## Token estimation from a file

The Calculator can fill its input-token field from an uploaded document: plain-text formats are read directly, PDF through `pdfjs-dist` loaded on demand.

This is an **estimate and never a count**, and the UI says so wherever the number appears. The SDKs in this repository stay out of token counting on the grounds that tokenizers differ across providers, and measurement backs that up: over a nine-document corpus, GPT-4o, GPT-4, Llama 3, Gemma and Claude disagree with each other by a median of 20% and by up to 61% on Japanese. No single figure can be correct for all of them.

The heuristic in `src/lib/estimate.ts` is a characters-per-token ratio adapted to the composition of the text — CJK characters count as roughly one token each, symbol-dense text such as JSON fragments into shorter tokens than prose. Its constants are fitted against those five tokenizers rather than chosen by feel: the central estimate stays within 15.3% of their mean, and the reported ±25% band contains 41 of the 45 reference counts. Per-language ratios would tighten this further and are the natural next step, since English measures 4.8 characters per token against Italian's 3.5.

`pdfjs-dist` is pinned to 4.x deliberately. pdf.js 5 and later require Safari 17.4, while Vite builds this app for `baseline-widely-available`, which reaches further back.

## Development

```bash
npm install
npm run dev        # local dev server
npm run lint
npm run test       # vitest
npm run typecheck  # weak here: tsconfig.json uses project references, so
                   # `tsc --noEmit` skips them. `npm run build` is the real gate.
npm run build      # production build (set GITHUB_PAGES=true for Pages base path)
```

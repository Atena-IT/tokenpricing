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

## Development

```bash
npm install
npm run dev        # local dev server
npm run lint
npm run typecheck
npm run build      # production build (set GITHUB_PAGES=true for Pages base path)
```

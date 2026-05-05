# tokenpricing

API pricing math for 1k+ AI models from [LLMTracker](https://mrunreal.github.io/LLMTracker) with multi-currency support.

## Libraries

| Library | Language | Package | Status |
|---------|----------|---------|--------|
| [Python SDK](libraries/python/) | Python 3.12+ | [`tokenpricing`](https://pypi.org/project/tokenpricing/) | Stable |
| [TypeScript SDK](libraries/typescript/) | TypeScript / Node 18+ | [`tokenpricing`](https://www.npmjs.com/package/tokenpricing) | Stable |

## Quick Start

### Python

```bash
pip install tokenpricing
```

```python
from tokenpricing import get_pricing_sync, compute_cost_sync

pricing = get_pricing_sync("openai/gpt-5.2", currency="EUR")
print(f"Input: €{pricing.input_per_million:.2f}/1M tokens")

cost = compute_cost_sync("openai/gpt-5.2", input_tokens=1000, output_tokens=500)
print(f"Total: ${cost:.6f}")
```

### TypeScript

```bash
npm install tokenpricing
```

```typescript
import { getPricing, computeCost } from "tokenpricing";

const pricing = await getPricing("openai/gpt-5.2", "EUR");
console.log(`Input: €${pricing.inputPerMillion.toFixed(2)}/1M tokens`);

const cost = await computeCost("openai/gpt-5.2", 1000, 500);
console.log(`Total: $${cost.toFixed(6)}`);
```

### CLI (Python)

Install via pip, then use the `tokenpricing` command.

```bash
# Show price per 1M tokens (USD default)
tokenpricing pricing openai/gpt-5.2

# Convert to another currency (uses cached FX rates)
tokenpricing pricing openai/gpt-5.2 --currency EUR

# JSON output for scripting
tokenpricing pricing openai/gpt-5.2 --json

# Compute total cost for a usage
tokenpricing cost openai/gpt-5.2 --in 1000 --out 500 --currency EUR
```

## Claude Code skill

This repository ships a Claude Code marketplace manifest at `.claude-plugin/marketplace.json` and the canonical hidden skill at `skills/tokenpricing/SKILL.md`.

When the plugin is installed, Claude Code can pick up the skill automatically and shell out to the existing `tokenpricing` CLI for pricing lookups and workload cost calculations.

The canonical skill source in this repository is `skills/tokenpricing/SKILL.md`.

## Data Source

Pricing data is sourced from [LLMTracker](https://github.com/MrUnreal/LLMTracker), which aggregates and updates pricing information from various LLM providers every six hours.

## Repository Structure

```
tokenpricing/
├── .claude-plugin/      Claude Code marketplace manifest
├── skills/              Canonical coding-agent skill
├── libraries/
│   ├── python/          Python SDK + CLI (PyPI)
│   └── typescript/      TypeScript SDK (npm)
├── .github/workflows/   CI/CD (path-filtered per library)
└── LICENSE
```

## Development

Each library is self-contained. See the individual READMEs for setup and development instructions:

- [Python SDK development](libraries/python/README.md#development)
- [TypeScript SDK development](libraries/typescript/README.md#development)

## Credits

- Pricing data: [LLMTracker](https://github.com/MrUnreal/LLMTracker) by MrUnreal

## License

See [LICENSE](LICENSE) file for details.

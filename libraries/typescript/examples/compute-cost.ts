import { computeCost, getPricing } from "tokenpricing";

const modelId = "openai/gpt-5.2";

// Get pricing info
const pricing = await getPricing(modelId, "EUR");
console.log(`Pricing for ${modelId} (${pricing.currency}):`);
console.log(`  Input per 1M tokens: €${pricing.inputPerMillion.toFixed(2)}`);
console.log(`  Output per 1M tokens: €${pricing.outputPerMillion.toFixed(2)}`);

// Compute total cost for a usage
const total = await computeCost(modelId, 1000, 500, "EUR");
console.log(`Total cost (EUR): €${total.toFixed(6)}`);

import { getPricing } from "tokenpricing";

const modelId = "openai/gpt-5.2";

const pricing = await getPricing(modelId);
console.log(`Pricing for ${modelId} (${pricing.currency}):`);
console.log(`  Input per 1M tokens: $${pricing.inputPerMillion.toFixed(2)}`);
console.log(`  Output per 1M tokens: $${pricing.outputPerMillion.toFixed(2)}`);

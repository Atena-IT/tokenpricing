import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatInteger(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

export function formatPrice(value?: number | null) {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: value >= 1 || value === 0 ? 2 : 4,
  }).format(value);
}

export function formatCompactTokens(value?: number | null) {
  if (!value) {
    return "—";
  }
  if (value >= 1_000_000) {
    return `${trimTrailingZero(value / 1_000_000)}M`;
  }
  if (value >= 1_000) {
    return `${trimTrailingZero(value / 1_000)}K`;
  }
  return formatInteger(value);
}

function trimTrailingZero(value: number) {
  return Number(value.toFixed(1)).toString();
}

export function formatRelativeTime(iso: string) {
  const timestamp = Date.parse(iso);
  if (Number.isNaN(timestamp)) {
    return "unknown";
  }
  const deltaSeconds = Math.round((timestamp - Date.now()) / 1000);
  const formatter = new Intl.RelativeTimeFormat("en-US", { numeric: "auto" });
  const divisions: Array<[number, Intl.RelativeTimeFormatUnit]> = [
    [60, "seconds"],
    [60, "minutes"],
    [24, "hours"],
    [7, "days"],
    [4.34524, "weeks"],
    [12, "months"],
    [Number.POSITIVE_INFINITY, "years"],
  ];
  let duration = deltaSeconds;
  for (const [amount, unit] of divisions) {
    if (Math.abs(duration) < amount) {
      return formatter.format(Math.round(duration), unit);
    }
    duration /= amount;
  }
  return "unknown";
}

export function formatModelTypeLabel(type: string) {
  const label = type.replace(/-/g, " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}

const PROVIDER_LABELS: Record<string, string> = {
  ai21: "AI21 Labs",
  aiml: "AI/ML API",
  allenai: "AllenAI",
  "aion-labs": "AionLabs",
  amazon: "Amazon",
  amazon_nova: "Amazon Nova",
  anthropic: "Anthropic",
  azure: "Azure OpenAI",
  bedrock: "AWS Bedrock",
  bedrock_converse: "AWS Bedrock",
  cerebras: "Cerebras",
  chatgpt: "OpenAI",
  cohere: "Cohere",
  databricks: "Databricks",
  deepinfra: "DeepInfra",
  deepseek: "DeepSeek",
  fireworks_ai: "Fireworks AI",
  gemini: "Google Gemini",
  google: "Google",
  groq: "Groq",
  huggingface: "Hugging Face",
  hyperbolic: "Hyperbolic",
  meta: "Meta",
  "meta-llama": "Meta Llama",
  mistral: "Mistral AI",
  mistralai: "Mistral AI",
  moonshotai: "Moonshot AI",
  nlp_cloud: "NLP Cloud",
  nvidia: "NVIDIA",
  ollama: "Ollama",
  openai: "OpenAI",
  openrouter: "OpenRouter",
  perplexity: "Perplexity",
  replicate: "Replicate",
  sambanova: "SambaNova",
  together_ai: "Together AI",
  togethercomputer: "Together AI",
  vertex_ai: "Vertex AI",
  voyage: "Voyage AI",
  watsonx: "IBM watsonx",
  publicai: "PublicAI",
  gradient_ai: "Gradient AI",
  xai: "xAI",
  "z-ai": "Z.ai",
};

export function formatProvider(slug: string) {
  const known = PROVIDER_LABELS[slug.toLowerCase()];
  if (known) {
    return known;
  }
  return slug
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

const NAME_ACRONYMS = new Set([
  "ai",
  "glm",
  "gpt",
  "hd",
  "llm",
  "moe",
  "sd",
  "sdxl",
  "tts",
  "ui",
  "vl",
  "xl",
]);

/**
 * LiteLLM-sourced records carry the provider slug as `display_name`; only
 * OpenRouter records have a humane name. Detect the degenerate case and build
 * a readable name from the model id instead.
 */
export function deriveModelName(model: { model_id: string; display_name?: string; provider: string }) {
  const declared = model.display_name?.trim() ?? "";
  const slugLike = /^[a-z0-9._/-]+$/.test(declared);
  if (declared && declared.toLowerCase() !== model.provider.toLowerCase() && !slugLike) {
    return declared;
  }

  const segments = model.model_id.split("/").filter(Boolean);
  const tail = segments[segments.length - 1] ?? model.model_id;
  const pretty = tail
    .split(/[-_]+/)
    .filter(Boolean)
    .map((token) => {
      if (NAME_ACRONYMS.has(token.toLowerCase())) {
        return token.toUpperCase();
      }
      if (/^\d/.test(token) || /^v\d/.test(token)) {
        return token;
      }
      return token.charAt(0).toUpperCase() + token.slice(1);
    })
    .join(" ");
  return pretty || model.model_id;
}

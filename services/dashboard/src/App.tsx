import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/700.css";
import "@fontsource/jetbrains-mono/500.css";

import { Activity, BrainCircuit, DatabaseZap, Layers3, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Badge } from "./components/ui/badge";
import { Card } from "./components/ui/card";
import { Input } from "./components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/tabs";
import { loadChangelogData, loadPricingData, type ChangelogData, type RawModelInfo } from "./lib/data";
import { formatInteger, formatPrice } from "./lib/utils";

function parseTokenCount(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function App() {
  const [models, setModels] = useState<RawModelInfo[]>([]);
  const [changelog, setChangelog] = useState<ChangelogData | null>(null);
  const [query, setQuery] = useState("");
  const [modelType, setModelType] = useState("all");
  const [compareA, setCompareA] = useState("");
  const [compareB, setCompareB] = useState("");
  const [calculatorModel, setCalculatorModel] = useState("");
  const [inputTokens, setInputTokens] = useState("1000000");
  const [outputTokens, setOutputTokens] = useState("500000");
  const [cacheReadTokens, setCacheReadTokens] = useState("0");
  const [cacheWriteTokens, setCacheWriteTokens] = useState("0");
  const [generatedAt, setGeneratedAt] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([loadPricingData(), loadChangelogData().catch(() => null)])
      .then(([pricingData, changelogData]) => {
        const entries = Object.values(pricingData.models);
        setModels(entries);
        setGeneratedAt(pricingData.generated_at);
        setCompareA(entries[0]?.model_id ?? "");
        setCompareB(entries[1]?.model_id ?? entries[0]?.model_id ?? "");
        setCalculatorModel(entries[0]?.model_id ?? "");
        setChangelog(changelogData);
      })
      .catch((loadError: Error) => {
        setError(loadError.message);
      });
  }, []);

  const filteredModels = useMemo(() => {
    const lowered = query.toLowerCase();
    return models
      .filter((model) => (modelType === "all" ? true : model.model_type === modelType))
      .filter((model) => {
        if (!lowered) {
          return true;
        }
        return [model.model_id, model.display_name, model.provider, model.category]
          .join(" ")
          .toLowerCase()
          .includes(lowered);
      })
      .slice(0, 40);
  }, [modelType, models, query]);

  const modelTypes = useMemo(
    () => ["all", ...Array.from(new Set(models.map((model) => model.model_type))).sort()],
    [models],
  );

  const highlightedModels = useMemo(
    () => models.filter((model) => [compareA, compareB].includes(model.model_id)),
    [compareA, compareB, models],
  );

  const costSummary = useMemo(() => {
    const model = models.find((entry) => entry.model_id === calculatorModel);
    if (!model) {
      return null;
    }
    const million = 1_000_000;
    const inputCost = (parseTokenCount(inputTokens) / million) * model.pricing.input_per_million;
    const outputCost = (parseTokenCount(outputTokens) / million) * model.pricing.output_per_million;
    const cacheReadCost =
      model.pricing.cache_read_per_million == null
        ? 0
        : (parseTokenCount(cacheReadTokens) / million) * model.pricing.cache_read_per_million;
    const cacheWriteCost =
      model.pricing.cache_creation_per_million == null
        ? 0
        : (parseTokenCount(cacheWriteTokens) / million) * model.pricing.cache_creation_per_million;
    return {
      inputCost,
      outputCost,
      cacheReadCost,
      cacheWriteCost,
      total: inputCost + outputCost + cacheReadCost + cacheWriteCost,
    };
  }, [cacheReadTokens, cacheWriteTokens, calculatorModel, inputTokens, models, outputTokens]);

  const chartData = highlightedModels.map((model) => ({
    name: model.display_name.replace(/^.+?:\s*/, ""),
    input: model.pricing.input_per_million,
    output: model.pricing.output_per_million,
    cacheRead: model.pricing.cache_read_per_million ?? 0,
    cacheWrite: model.pricing.cache_creation_per_million ?? 0,
  }));

  const cacheEnabledCount = models.filter(
    (model) => model.pricing.cache_read_per_million != null || model.pricing.cache_creation_per_million != null,
  ).length;

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.18),_transparent_35%),linear-gradient(180deg,_#020617,_#020617_40%,_#111827)] px-4 py-10 text-slate-50 md:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-8">
        <section className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
          <Card className="relative overflow-hidden">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,_rgba(45,212,191,0.22),_transparent_30%)]" />
            <div className="relative flex flex-col gap-5">
              <Badge className="w-fit">Canonical model pricing, now fully in-repo</Badge>
              <div className="flex flex-col gap-3">
                <h1 className="max-w-3xl text-4xl font-semibold tracking-tight md:text-5xl">
                  tokenpricing dashboard
                </h1>
                <p className="max-w-3xl text-base text-slate-300 md:text-lg">
                  Restored from the original LLMTracker experience, rebuilt on a modern Vite + React stack with curated shadcn-style primitives, first-class cache-token pricing, and a canonical dataset for AI model types published from this repository.
                </p>
              </div>
              <div className="flex flex-wrap gap-3 text-sm text-slate-300">
                <span>Generated {generatedAt ? new Date(generatedAt).toLocaleString() : "…"}</span>
                <span>•</span>
                <span>{formatInteger(models.length)} models live</span>
                <span>•</span>
                <span>{formatInteger(cacheEnabledCount)} with cache pricing</span>
              </div>
            </div>
          </Card>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
            <MetricCard icon={Layers3} label="Models" value={formatInteger(models.length)} helper="Combined OpenRouter + LiteLLM catalog" />
            <MetricCard icon={DatabaseZap} label="Cache-aware" value={formatInteger(cacheEnabledCount)} helper="Models exposing cache read or write pricing" />
            <MetricCard icon={BrainCircuit} label="Providers" value={formatInteger(new Set(models.map((model) => model.provider)).size)} helper="Canonical provider registry baked into the dataset" />
          </div>
        </section>

        {error ? <Card className="border-rose-400/30 text-rose-200">{error}</Card> : null}

        <Tabs defaultValue="explore" className="flex flex-col gap-6">
          <TabsList>
            <TabsTrigger value="explore">Explorer</TabsTrigger>
            <TabsTrigger value="compare">Compare</TabsTrigger>
            <TabsTrigger value="calculator">Calculator</TabsTrigger>
            <TabsTrigger value="changelog">Changelog</TabsTrigger>
          </TabsList>

          <TabsContent value="explore">
            <Card className="flex flex-col gap-6">
              <div className="grid gap-4 md:grid-cols-[1fr_220px]">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-4 top-3.5 h-4 w-4 text-slate-400" />
                  <Input className="pl-11" placeholder="Search by model, provider, or category" value={query} onChange={(event) => setQuery(event.target.value)} />
                </div>
                <Select value={modelType} onValueChange={setModelType}>
                  <SelectTrigger>
                    <SelectValue placeholder="Filter by type" />
                  </SelectTrigger>
                  <SelectContent>
                    {modelTypes.map((type) => (
                      <SelectItem key={type} value={type}>
                        {type}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="overflow-x-auto rounded-3xl border border-white/10">
                <table className="min-w-full divide-y divide-white/10 text-left text-sm">
                  <thead className="bg-white/5 text-slate-300">
                    <tr>
                      <th className="px-4 py-3 font-medium">Model</th>
                      <th className="px-4 py-3 font-medium">Type</th>
                      <th className="px-4 py-3 font-medium">Input / 1M</th>
                      <th className="px-4 py-3 font-medium">Output / 1M</th>
                      <th className="px-4 py-3 font-medium">Cache read</th>
                      <th className="px-4 py-3 font-medium">Cache write</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {filteredModels.map((model) => (
                      <tr key={model.model_id} className="hover:bg-white/5">
                        <td className="px-4 py-3">
                          <div className="font-medium text-slate-50">{model.display_name}</div>
                          <div className="font-mono text-xs text-slate-400">{model.model_id}</div>
                        </td>
                        <td className="px-4 py-3 text-slate-300">{model.model_type}</td>
                        <td className="px-4 py-3 text-slate-200">{formatPrice(model.pricing.input_per_million)}</td>
                        <td className="px-4 py-3 text-slate-200">{formatPrice(model.pricing.output_per_million)}</td>
                        <td className="px-4 py-3 text-slate-200">{formatPrice(model.pricing.cache_read_per_million ?? undefined)}</td>
                        <td className="px-4 py-3 text-slate-200">{formatPrice(model.pricing.cache_creation_per_million ?? undefined)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </TabsContent>

          <TabsContent value="compare">
            <Card className="flex flex-col gap-6">
              <div className="grid gap-4 md:grid-cols-2">
                <ModelSelector label="Left model" models={models} value={compareA} onChange={setCompareA} />
                <ModelSelector label="Right model" models={models} value={compareB} onChange={setCompareB} />
              </div>
              <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
                <div className="grid gap-4 sm:grid-cols-2">
                  {highlightedModels.map((model) => (
                    <Card key={model.model_id} className="border-white/5 bg-white/5">
                      <div className="mb-3 flex items-center justify-between gap-4">
                        <div>
                          <div className="text-lg font-medium">{model.display_name}</div>
                          <div className="font-mono text-xs text-slate-400">{model.model_id}</div>
                        </div>
                        <Badge>{model.model_type}</Badge>
                      </div>
                      <div className="space-y-2 text-sm text-slate-300">
                        <DetailRow label="Input" value={formatPrice(model.pricing.input_per_million)} />
                        <DetailRow label="Output" value={formatPrice(model.pricing.output_per_million)} />
                        <DetailRow label="Cache read" value={formatPrice(model.pricing.cache_read_per_million ?? undefined)} />
                        <DetailRow label="Cache write" value={formatPrice(model.pricing.cache_creation_per_million ?? undefined)} />
                        <DetailRow label="Context" value={formatInteger(model.context_window)} />
                      </div>
                    </Card>
                  ))}
                </div>
                <Card className="border-white/5 bg-white/5">
                  <div className="mb-4 flex items-center gap-2 text-sm text-slate-300">
                    <Activity className="h-4 w-4 text-cyan-300" />
                    Price surface per million tokens
                  </div>
                  <div className="h-[320px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={chartData} margin={{ top: 10, right: 0, left: 0, bottom: 0 }}>
                        <defs>
                          <linearGradient id="inputFill" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.8} />
                            <stop offset="95%" stopColor="#22d3ee" stopOpacity={0} />
                          </linearGradient>
                          <linearGradient id="outputFill" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#a855f7" stopOpacity={0.8} />
                            <stop offset="95%" stopColor="#a855f7" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                        <XAxis dataKey="name" stroke="#94a3b8" />
                        <YAxis stroke="#94a3b8" />
                        <Tooltip contentStyle={{ backgroundColor: "#020617", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 16 }} />
                        <Area type="monotone" dataKey="input" stroke="#22d3ee" fill="url(#inputFill)" />
                        <Area type="monotone" dataKey="output" stroke="#a855f7" fill="url(#outputFill)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </Card>
              </div>
            </Card>
          </TabsContent>

          <TabsContent value="calculator">
            <Card className="grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
              <div className="space-y-4">
                <ModelSelector label="Model" models={models} value={calculatorModel} onChange={setCalculatorModel} />
                <Input type="number" value={inputTokens} onChange={(event) => setInputTokens(event.target.value)} placeholder="Input tokens" />
                <Input type="number" value={outputTokens} onChange={(event) => setOutputTokens(event.target.value)} placeholder="Output tokens" />
                <Input type="number" value={cacheReadTokens} onChange={(event) => setCacheReadTokens(event.target.value)} placeholder="Cache read tokens" />
                <Input type="number" value={cacheWriteTokens} onChange={(event) => setCacheWriteTokens(event.target.value)} placeholder="Cache write tokens" />
              </div>
              <Card className="border-white/5 bg-white/5">
                <div className="mb-4 text-sm text-slate-300">Usage estimate in the model's published currency.</div>
                {costSummary ? (
                  <div className="space-y-4">
                    <DetailRow label="Input cost" value={formatPrice(costSummary.inputCost)} />
                    <DetailRow label="Output cost" value={formatPrice(costSummary.outputCost)} />
                    <DetailRow label="Cache read cost" value={formatPrice(costSummary.cacheReadCost)} />
                    <DetailRow label="Cache write cost" value={formatPrice(costSummary.cacheWriteCost)} />
                    <div className="h-px bg-white/10" />
                    <DetailRow label="Total" value={formatPrice(costSummary.total)} emphasized />
                  </div>
                ) : (
                  <div className="text-slate-400">Pick a model to start.</div>
                )}
              </Card>
            </Card>
          </TabsContent>

          <TabsContent value="changelog">
            <Card className="flex flex-col gap-6">
              <div className="grid gap-4 md:grid-cols-4">
                <MetricCard icon={Layers3} label="Added" value={String(changelog?.summary.model_additions ?? 0)} helper="New models since the previous snapshot" compact />
                <MetricCard icon={Layers3} label="Removed" value={String(changelog?.summary.model_removals ?? 0)} helper="Models no longer present upstream" compact />
                <MetricCard icon={Activity} label="Pricing" value={String(changelog?.summary.pricing_changes ?? 0)} helper="Input/output price moves" compact />
                <MetricCard icon={DatabaseZap} label="Cache" value={String(changelog?.summary.cache_price_changes ?? 0)} helper="Cache read/write price moves" compact />
              </div>
              <div className="space-y-3">
                {(changelog?.changes ?? []).slice(0, 20).map((change, index) => (
                  <Card key={`${String(change.type)}-${index}`} className="border-white/5 bg-white/5 p-4">
                    <div className="mb-2 flex items-center justify-between gap-4">
                      <Badge className="bg-cyan-400/10 text-cyan-100">{String(change.type)}</Badge>
                      <span className="text-xs uppercase tracking-[0.2em] text-slate-400">{String(change.model_type ?? "n/a")}</span>
                    </div>
                    <div className="font-mono text-sm text-slate-200">{String(change.model_id)}</div>
                  </Card>
                ))}
                {!changelog ? <div className="text-slate-400">No changelog snapshot available yet.</div> : null}
              </div>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </main>
  );
}

function MetricCard({ icon: Icon, label, value, helper, compact = false }: { icon: typeof Layers3; label: string; value: string; helper: string; compact?: boolean; }) {
  return (
    <Card className="flex items-start gap-4">
      <div className="rounded-2xl bg-cyan-400/10 p-3 text-cyan-200">
        <Icon className="h-5 w-5" />
      </div>
      <div className="space-y-1">
        <div className="text-sm text-slate-400">{label}</div>
        <div className={compact ? "text-2xl font-semibold" : "text-3xl font-semibold"}>{value}</div>
        <div className="max-w-xs text-sm text-slate-400">{helper}</div>
      </div>
    </Card>
  );
}

function ModelSelector({ label, models, value, onChange }: { label: string; models: RawModelInfo[]; value: string; onChange: (value: string) => void; }) {
  return (
    <div className="space-y-2">
      <div className="text-sm text-slate-300">{label}</div>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue placeholder="Select a model" />
        </SelectTrigger>
        <SelectContent>
          {models.slice(0, 300).map((model) => (
            <SelectItem key={model.model_id} value={model.model_id}>
              {model.display_name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function DetailRow({ label, value, emphasized = false }: { label: string; value: string; emphasized?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-slate-400">{label}</span>
      <span className={emphasized ? "font-semibold text-cyan-200" : "font-medium text-slate-100"}>{value}</span>
    </div>
  );
}

export default App;

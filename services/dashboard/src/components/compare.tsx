import { Eye, Wrench, Zap, type LucideIcon } from "lucide-react";
import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { ModelRow } from "../lib/data";
import { cn, formatCompactTokens, formatPrice } from "../lib/utils";
import { Badge } from "./ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Combobox, type ComboboxOption } from "./ui/combobox";

export function buildModelOptions(models: ModelRow[]): ComboboxOption[] {
  return models.map((model) => ({
    value: model.model_id,
    label: `${model.name} · ${model.providerLabel}`,
    hint: model.model_id,
  }));
}

export function CompareView({
  models,
  options,
  modelA,
  modelB,
  onChangeA,
  onChangeB,
}: {
  models: ModelRow[];
  options: ComboboxOption[];
  modelA: string;
  modelB: string;
  onChangeA: (value: string) => void;
  onChangeB: (value: string) => void;
}) {
  const left = useMemo(() => models.find((model) => model.model_id === modelA), [modelA, models]);
  const right = useMemo(() => models.find((model) => model.model_id === modelB), [modelB, models]);

  const chartData = useMemo(() => {
    if (!left || !right) {
      return [];
    }
    const metrics: Array<{ metric: string; a: number | null; b: number | null }> = [
      { metric: "Input", a: left.pricing.input_per_million, b: right.pricing.input_per_million },
      { metric: "Output", a: left.pricing.output_per_million, b: right.pricing.output_per_million },
      { metric: "Cache read", a: left.pricing.cache_read_per_million, b: right.pricing.cache_read_per_million },
      {
        metric: "Cache write",
        a: left.pricing.cache_creation_per_million,
        b: right.pricing.cache_creation_per_million,
      },
    ];
    return metrics.filter((entry) => entry.a != null || entry.b != null);
  }, [left, right]);

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-muted-foreground">Model A</label>
          <Combobox options={options} value={modelA} onChange={onChangeA} placeholder="Pick a model" searchPlaceholder="Search 3,000+ models…" />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-muted-foreground">Model B</label>
          <Combobox options={options} value={modelB} onChange={onChangeB} placeholder="Pick a model" searchPlaceholder="Search 3,000+ models…" />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ModelSpecCard model={left} accent="chart-1" />
        <ModelSpecCard model={right} accent="chart-2" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Price per million tokens</CardTitle>
          <CardDescription>{summarize(left, right)}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 4 }} barCategoryGap="24%">
                <CartesianGrid stroke="var(--border)" horizontal={false} />
                <XAxis
                  type="number"
                  stroke="var(--muted-foreground)"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(value: number) => formatPrice(value)}
                />
                <YAxis
                  type="category"
                  dataKey="metric"
                  stroke="var(--muted-foreground)"
                  fontSize={12}
                  width={86}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  cursor={{ fill: "color-mix(in srgb, var(--muted-foreground) 8%, transparent)" }}
                  contentStyle={{
                    backgroundColor: "var(--popover)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    color: "var(--popover-foreground)",
                    fontSize: 13,
                  }}
                  formatter={(value) => formatPrice(typeof value === "number" ? value : Number(value))}
                />
                <Legend wrapperStyle={{ fontSize: 13 }} />
                <Bar dataKey="a" name={left?.name ?? "Model A"} fill="var(--chart-1)" radius={[0, 4, 4, 0]} maxBarSize={18} />
                <Bar dataKey="b" name={right?.name ?? "Model B"} fill="var(--chart-2)" radius={[0, 4, 4, 0]} maxBarSize={18} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function summarize(left?: ModelRow, right?: ModelRow) {
  if (!left || !right) {
    return "Pick two models to compare their published rates.";
  }
  const leftInput = left.pricing.input_per_million;
  const rightInput = right.pricing.input_per_million;
  if (!leftInput || !rightInput || leftInput === rightInput) {
    return "Published USD rates per million tokens.";
  }
  const cheaper = leftInput < rightInput ? left : right;
  const ratio = Math.max(leftInput, rightInput) / Math.min(leftInput, rightInput);
  return `Input tokens on ${cheaper.name} are ${ratio.toFixed(1)}× cheaper.`;
}

function ModelSpecCard({ model, accent }: { model?: ModelRow; accent: "chart-1" | "chart-2" }) {
  if (!model) {
    return (
      <Card className="flex items-center justify-center p-10 text-sm text-muted-foreground">
        No model selected
      </Card>
    );
  }
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
        <div className="flex min-w-0 items-start gap-2.5">
          <span
            className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full"
            style={{ backgroundColor: `var(--${accent})` }}
            aria-hidden
          />
          <div className="min-w-0">
            <CardTitle className="truncate text-base">{model.name}</CardTitle>
            <CardDescription className="mt-1 truncate font-mono text-xs">{model.model_id}</CardDescription>
          </div>
        </div>
        <Badge variant="outline" className="shrink-0">
          {model.providerLabel}
        </Badge>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 text-sm">
        <SpecRow label="Input / 1M" value={formatPrice(model.pricing.input_per_million)} />
        <SpecRow label="Output / 1M" value={formatPrice(model.pricing.output_per_million)} />
        <SpecRow label="Cache read / 1M" value={formatPrice(model.pricing.cache_read_per_million)} />
        <SpecRow label="Cache write / 1M" value={formatPrice(model.pricing.cache_creation_per_million)} />
        <div className="my-1 border-t" />
        <SpecRow label="Context window" value={formatCompactTokens(model.context_window)} />
        <SpecRow label="Max output" value={formatCompactTokens(model.max_output_tokens)} />
        <div className="mt-2 flex flex-wrap gap-1.5">
          <CapabilityBadge icon={Eye} label="Vision" supported={model.supports_vision} />
          <CapabilityBadge icon={Wrench} label="Tools" supported={model.supports_function_calling} />
          <CapabilityBadge icon={Zap} label="Streaming" supported={model.supports_streaming} />
        </div>
      </CardContent>
    </Card>
  );
}

function SpecRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium tabular-nums">{value}</span>
    </div>
  );
}

function CapabilityBadge({ icon: Icon, label, supported }: { icon: LucideIcon; label: string; supported: boolean }) {
  return (
    <Badge variant={supported ? "primary" : "outline"} className={cn(!supported && "opacity-50")}>
      <Icon className="h-3 w-3" />
      {label}
    </Badge>
  );
}

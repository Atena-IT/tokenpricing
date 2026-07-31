import { Info } from "lucide-react";
import { useMemo, useState, type ChangeEvent } from "react";

import type { ModelRow } from "../lib/data";
import { formatInteger, formatPrice } from "../lib/utils";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { FileEstimate } from "./file-estimate";
import { Combobox, type ComboboxOption } from "./ui/combobox";
import { Input } from "./ui/input";

interface Usage {
  input: string;
  output: string;
  cacheRead: string;
  cacheWrite: string;
}

const PRESETS: Array<{ label: string; usage: Usage }> = [
  { label: "Chat turn", usage: { input: "2000", output: "500", cacheRead: "0", cacheWrite: "0" } },
  {
    label: "Agent session",
    usage: { input: "250000", output: "25000", cacheRead: "500000", cacheWrite: "50000" },
  },
  { label: "Batch pipeline", usage: { input: "10000000", output: "2000000", cacheRead: "0", cacheWrite: "0" } },
];

function parseTokens(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

export function CalculatorView({
  models,
  options,
  selected,
  onSelect,
}: {
  models: ModelRow[];
  options: ComboboxOption[];
  selected: string;
  onSelect: (value: string) => void;
}) {
  const [usage, setUsage] = useState<Usage>({
    input: "1000000",
    output: "500000",
    cacheRead: "0",
    cacheWrite: "0",
  });

  const model = useMemo(() => models.find((entry) => entry.model_id === selected), [models, selected]);

  const summary = useMemo(() => {
    if (!model) {
      return null;
    }
    const million = 1_000_000;
    const lines = [
      {
        label: "Input",
        tokens: parseTokens(usage.input),
        rate: model.pricing.input_per_million as number | null,
      },
      {
        label: "Output",
        tokens: parseTokens(usage.output),
        rate: model.pricing.output_per_million as number | null,
      },
      { label: "Cache read", tokens: parseTokens(usage.cacheRead), rate: model.pricing.cache_read_per_million },
      {
        label: "Cache write",
        tokens: parseTokens(usage.cacheWrite),
        rate: model.pricing.cache_creation_per_million,
      },
    ].map((line) => ({ ...line, cost: line.rate == null ? 0 : (line.tokens / million) * line.rate }));
    const unpricedCache = lines.some((line) => line.rate == null && line.tokens > 0);
    return { lines, total: lines.reduce((sum, line) => sum + line.cost, 0), unpricedCache };
  }, [model, usage]);

  const setField = (field: keyof Usage) => (event: ChangeEvent<HTMLInputElement>) =>
    setUsage((current) => ({ ...current, [field]: event.target.value }));

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
      <Card>
        <CardHeader>
          <CardTitle>Workload</CardTitle>
          <CardDescription>Token usage to price against the selected model.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-muted-foreground">Model</label>
            <Combobox
              options={options}
              value={selected}
              onChange={onSelect}
              placeholder="Pick a model"
              searchPlaceholder="Search 3,000+ models…"
            />
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Presets</span>
            {PRESETS.map((preset) => (
              <Button key={preset.label} variant="outline" size="sm" onClick={() => setUsage(preset.usage)}>
                {preset.label}
              </Button>
            ))}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <TokenField label="Input tokens" value={usage.input} onChange={setField("input")} />
            <TokenField label="Output tokens" value={usage.output} onChange={setField("output")} />
            <TokenField label="Cache read tokens" value={usage.cacheRead} onChange={setField("cacheRead")} />
            <TokenField label="Cache write tokens" value={usage.cacheWrite} onChange={setField("cacheWrite")} />
          </div>
          <FileEstimate onEstimate={(tokens) => setUsage((current) => ({ ...current, input: String(tokens) }))} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Estimated cost</CardTitle>
          <CardDescription>
            {model ? `${model.name} · published USD rates per million tokens` : "Pick a model to start."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {summary && model ? (
            <div className="flex flex-col gap-3">
              {summary.lines.map((line) => (
                <div key={line.label} className="flex items-baseline justify-between gap-4 text-sm">
                  <div>
                    <div className="font-medium">{line.label}</div>
                    <div className="text-xs text-muted-foreground tabular-nums">
                      {formatInteger(line.tokens)} tokens × {line.rate == null ? "n/a" : `${formatPrice(line.rate)}/1M`}
                    </div>
                  </div>
                  <span className="font-medium tabular-nums">
                    {line.rate == null && line.tokens > 0 ? "—" : formatPrice(line.cost)}
                  </span>
                </div>
              ))}
              <div className="border-t" />
              <div className="flex items-baseline justify-between gap-4">
                <span className="text-sm font-medium">Total</span>
                <span className="text-2xl font-semibold tracking-tight tabular-nums">
                  {formatPrice(summary.total)}
                </span>
              </div>
              {summary.unpricedCache ? (
                <p className="m-0 flex items-start gap-2 rounded-md bg-warning/10 p-3 text-xs text-warning">
                  <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  This model does not publish cache token rates, so cache tokens are excluded from the total.
                </p>
              ) : null}
            </div>
          ) : (
            <p className="m-0 py-8 text-center text-sm text-muted-foreground">Pick a model to see the estimate.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function TokenField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-muted-foreground">{label}</label>
      <Input type="number" min="0" inputMode="numeric" value={value} onChange={onChange} className="tabular-nums" />
    </div>
  );
}

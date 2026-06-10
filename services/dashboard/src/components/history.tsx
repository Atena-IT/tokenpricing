import { AlertCircle, History as HistoryIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { loadHistorySnapshots, type HistorySnapshot, type ModelRow, type RawPricingInfo } from "../lib/data";
import { formatPrice } from "../lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Combobox, type ComboboxOption } from "./ui/combobox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Skeleton } from "./ui/skeleton";

const METRICS: Array<{ key: string; label: string; read: (pricing: RawPricingInfo) => number | null }> = [
  { key: "input", label: "Input / 1M", read: (pricing) => pricing.input_per_million },
  { key: "output", label: "Output / 1M", read: (pricing) => pricing.output_per_million },
  { key: "cacheRead", label: "Cache read / 1M", read: (pricing) => pricing.cache_read_per_million },
  { key: "cacheWrite", label: "Cache write / 1M", read: (pricing) => pricing.cache_creation_per_million },
];

/** The snapshot set is immutable per page load — fetch it once, lazily. */
let snapshotsPromise: Promise<HistorySnapshot[]> | null = null;

function fetchSnapshotsOnce() {
  snapshotsPromise ??= loadHistorySnapshots().catch((error: Error) => {
    snapshotsPromise = null;
    throw error;
  });
  return snapshotsPromise;
}

function formatSnapshotTick(timestamp: string) {
  return new Date(timestamp).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatSnapshotLabel(timestamp: string) {
  return new Date(timestamp).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function HistoryView({
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
  const [snapshots, setSnapshots] = useState<HistorySnapshot[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [metric, setMetric] = useState("input");

  useEffect(() => {
    let cancelled = false;
    fetchSnapshotsOnce()
      .then((loaded) => {
        if (!cancelled) {
          setSnapshots(loaded);
        }
      })
      .catch((loadError: Error) => {
        if (!cancelled) {
          setError(loadError.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const left = useMemo(() => models.find((model) => model.model_id === modelA), [modelA, models]);
  const right = useMemo(() => models.find((model) => model.model_id === modelB), [modelB, models]);
  const readMetric = METRICS.find((entry) => entry.key === metric)?.read ?? METRICS[0].read;

  const chartData = useMemo(() => {
    if (!snapshots) {
      return [];
    }
    return snapshots.map((snapshot) => {
      const pricingA = snapshot.models[modelA]?.pricing;
      const pricingB = snapshot.models[modelB]?.pricing;
      return {
        timestamp: snapshot.timestamp,
        a: pricingA ? readMetric(pricingA) : null,
        b: pricingB ? readMetric(pricingB) : null,
      };
    });
  }, [modelA, modelB, readMetric, snapshots]);

  const trend = useMemo(() => {
    const series = chartData.map((point) => point.a).filter((value): value is number => value != null);
    if (!left || series.length < 2) {
      return null;
    }
    const [first, last] = [series[0], series[series.length - 1]];
    if (first === last) {
      return `${left.name} has held steady across ${series.length} snapshots.`;
    }
    const direction = last > first ? "up" : "down";
    const percent = first === 0 ? null : Math.abs(((last - first) / first) * 100);
    return `${left.name} moved ${direction} from ${formatPrice(first)} to ${formatPrice(last)}${
      percent == null ? "" : ` (${percent.toFixed(1)}%)`
    }.`;
  }, [chartData, left]);

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 md:grid-cols-[1fr_1fr_220px]">
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-muted-foreground">Model A</label>
          <Combobox options={options} value={modelA} onChange={onChangeA} placeholder="Pick a model" searchPlaceholder="Search 3,000+ models…" />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-muted-foreground">Model B</label>
          <Combobox options={options} value={modelB} onChange={onChangeB} placeholder="Pick a model" searchPlaceholder="Search 3,000+ models…" />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-muted-foreground">Metric</label>
          <Select value={metric} onValueChange={setMetric}>
            <SelectTrigger aria-label="Price metric">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {METRICS.map((entry) => (
                <SelectItem key={entry.key} value={entry.key}>
                  {entry.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Price history</CardTitle>
          <CardDescription>
            {snapshots
              ? trend ??
                `${snapshots.length} snapshot${snapshots.length === 1 ? "" : "s"} from the canonical database, captured every six hours.`
              : "Loading snapshots from the canonical database…"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error ? (
            <div className="flex items-center gap-2 py-10 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              Could not load price history: {error}
            </div>
          ) : !snapshots ? (
            <div className="flex flex-col gap-3 py-4">
              <Skeleton className="h-56 w-full" />
              <Skeleton className="h-4 w-64" />
            </div>
          ) : snapshots.length < 2 ? (
            <div className="flex flex-col items-center gap-2 py-12 text-center">
              <HistoryIcon className="h-7 w-7 text-muted-foreground" />
              <p className="m-0 text-sm font-medium">Not enough history yet</p>
              <p className="m-0 text-sm text-muted-foreground">
                The database stores a snapshot every six hours — the chart fills in as history accumulates.
              </p>
            </div>
          ) : (
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 4 }}>
                  <CartesianGrid stroke="var(--border)" vertical={false} />
                  <XAxis
                    dataKey="timestamp"
                    stroke="var(--muted-foreground)"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={formatSnapshotTick}
                  />
                  <YAxis
                    stroke="var(--muted-foreground)"
                    fontSize={12}
                    width={72}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value: number) => formatPrice(value)}
                    domain={["auto", "auto"]}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--popover)",
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                      color: "var(--popover-foreground)",
                      fontSize: 13,
                    }}
                    labelFormatter={(value) => formatSnapshotLabel(String(value))}
                    formatter={(value) => formatPrice(typeof value === "number" ? value : Number(value))}
                  />
                  <Legend wrapperStyle={{ fontSize: 13 }} />
                  <Line
                    type="monotone"
                    dataKey="a"
                    name={left?.name ?? "Model A"}
                    stroke="var(--chart-1)"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    connectNulls
                  />
                  <Line
                    type="monotone"
                    dataKey="b"
                    name={right?.name ?? "Model B"}
                    stroke="var(--chart-2)"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

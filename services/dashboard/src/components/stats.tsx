import { Building2, DatabaseZap, Layers, RefreshCw, type LucideIcon } from "lucide-react";

import type { ModelRow } from "../lib/data";
import { formatInteger, formatRelativeTime } from "../lib/utils";
import { Card } from "./ui/card";
import { Skeleton } from "./ui/skeleton";

export function StatsRow({ models, generatedAt, loading }: { models: ModelRow[]; generatedAt: string; loading: boolean }) {
  if (loading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Card key={index} className="p-5">
            <Skeleton className="mb-3 h-4 w-24" />
            <Skeleton className="h-7 w-16" />
          </Card>
        ))}
      </div>
    );
  }

  const providerCount = new Set(models.map((model) => model.provider)).size;
  const cacheAwareCount = models.filter(
    (model) => model.pricing.cache_read_per_million != null || model.pricing.cache_creation_per_million != null,
  ).length;
  const cacheShare = models.length ? Math.round((cacheAwareCount / models.length) * 100) : 0;

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard icon={Layers} label="Models tracked" value={formatInteger(models.length)} detail="OpenRouter + LiteLLM catalogs" />
      <StatCard icon={Building2} label="Providers" value={formatInteger(providerCount)} detail="Canonical provider registry" />
      <StatCard
        icon={DatabaseZap}
        label="Cache-aware models"
        value={formatInteger(cacheAwareCount)}
        detail={`${cacheShare}% publish cache read/write rates`}
      />
      <StatCard
        icon={RefreshCw}
        label="Last sync"
        value={generatedAt ? formatRelativeTime(generatedAt) : "—"}
        detail={generatedAt ? new Date(generatedAt).toLocaleString("en-US") : "Awaiting first snapshot"}
      />
    </div>
  );
}

function StatCard({ icon: Icon, label, value, detail }: { icon: LucideIcon; label: string; value: string; detail: string }) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-muted-foreground">{label}</span>
        <Icon className="h-4 w-4 text-muted-foreground" aria-hidden />
      </div>
      <div className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">{value}</div>
      <div className="mt-1 truncate text-xs text-muted-foreground">{detail}</div>
    </Card>
  );
}

import { ArrowDownUp, CheckCircle2, DatabaseZap, Minus, Plus, type LucideIcon } from "lucide-react";

import type { ChangelogData } from "../lib/data";
import { cn, formatModelTypeLabel, formatRelativeTime } from "../lib/utils";
import { Badge } from "./ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

const CHANGE_BADGES: Record<string, { label: string; variant: "success" | "destructive" | "warning" | "primary" }> = {
  model_added: { label: "Added", variant: "success" },
  model_removed: { label: "Removed", variant: "destructive" },
  pricing_changed: { label: "Pricing", variant: "warning" },
  cache_price_changed: { label: "Cache", variant: "primary" },
};

export function ChangelogView({ changelog }: { changelog: ChangelogData | null }) {
  const summary = changelog?.summary;
  const changes = changelog?.changes ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <ChangeStat icon={Plus} tone="text-success" label="Models added" value={summary?.model_additions ?? 0} />
        <ChangeStat icon={Minus} tone="text-destructive" label="Models removed" value={summary?.model_removals ?? 0} />
        <ChangeStat icon={ArrowDownUp} tone="text-warning" label="Price changes" value={summary?.pricing_changes ?? 0} />
        <ChangeStat icon={DatabaseZap} tone="text-primary" label="Cache changes" value={summary?.cache_price_changes ?? 0} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Latest sync window</CardTitle>
        </CardHeader>
        <CardContent>
          {changes.length > 0 ? (
            <ul className="m-0 flex list-none flex-col divide-y p-0">
              {changes.map((change, index) => {
                const badge = CHANGE_BADGES[change.type] ?? { label: change.type, variant: "primary" as const };
                return (
                  <li key={`${change.type}-${change.model_id}-${index}`} className="flex items-center gap-3 py-2.5">
                    <Badge variant={badge.variant} className="min-w-20 shrink-0 justify-center">
                      {badge.label}
                    </Badge>
                    <span className="min-w-0 flex-1 truncate font-mono text-sm">{change.model_id}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {change.model_type ? formatModelTypeLabel(change.model_type) : ""}
                    </span>
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className="flex flex-col items-center gap-2 py-12 text-center">
              <CheckCircle2 className="h-7 w-7 text-success" />
              <p className="m-0 text-sm font-medium">Pricing is stable</p>
              <p className="m-0 text-sm text-muted-foreground">
                No additions, removals, or price moves in the latest sync
                {changelog ? ` (${formatRelativeTime(changelog.generated_at)})` : ""}.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ChangeStat({ icon: Icon, tone, label, value }: { icon: LucideIcon; tone: string; label: string; value: number }) {
  return (
    <Card className="flex items-center gap-3 p-4">
      <div className={cn("rounded-md bg-muted p-2", tone)}>
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <div className="text-xl font-semibold leading-tight tabular-nums">{value}</div>
        <div className="text-xs text-muted-foreground">{label}</div>
      </div>
    </Card>
  );
}

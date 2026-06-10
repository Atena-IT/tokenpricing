import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type Column,
  type ColumnDef,
  type RowData,
  type SortingState,
} from "@tanstack/react-table";

declare module "@tanstack/react-table" {
  // The type parameters are required to match the upstream declaration.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData extends RowData, TValue> {
    align?: "left" | "right";
  }
}
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Search, SearchX } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import type { ModelRow } from "../lib/data";
import { cn, formatCompactTokens, formatInteger, formatModelTypeLabel, formatPrice } from "../lib/utils";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";

const PAGE_SIZES = [25, 50, 100];

function SortableHeader({ column, children, align = "left" }: { column: Column<ModelRow, unknown>; children: ReactNode; align?: "left" | "right" }) {
  const direction = column.getIsSorted();
  const Icon = direction === "asc" ? ArrowUp : direction === "desc" ? ArrowDown : ArrowUpDown;
  return (
    <button
      type="button"
      onClick={column.getToggleSortingHandler()}
      className={cn(
        "-mx-1.5 inline-flex h-7 items-center gap-1 rounded-md px-1.5 text-xs font-medium uppercase tracking-wide transition-colors hover:text-foreground",
        align === "right" && "flex-row-reverse",
        direction ? "text-foreground" : "text-muted-foreground",
      )}
    >
      {children}
      <Icon className={cn("h-3.5 w-3.5", !direction && "opacity-50")} />
    </button>
  );
}

const priceCell = (value: number | null | undefined) =>
  value == null ? (
    <span className="text-muted-foreground/60">—</span>
  ) : (
    <span className="tabular-nums">{formatPrice(value)}</span>
  );

const columns: ColumnDef<ModelRow>[] = [
  {
    id: "model",
    accessorKey: "name",
    header: ({ column }) => <SortableHeader column={column}>Model</SortableHeader>,
    cell: ({ row }) => (
      <div className="min-w-0 max-w-[26rem]">
        <div className="truncate font-medium text-foreground">{row.original.name}</div>
        <div className="truncate font-mono text-xs text-muted-foreground">{row.original.model_id}</div>
      </div>
    ),
  },
  {
    id: "provider",
    accessorKey: "providerLabel",
    header: ({ column }) => <SortableHeader column={column}>Provider</SortableHeader>,
    cell: ({ getValue }) => <span className="whitespace-nowrap text-muted-foreground">{getValue<string>()}</span>,
  },
  {
    id: "type",
    accessorKey: "model_type",
    header: () => <span>Type</span>,
    enableSorting: false,
    cell: ({ getValue }) => (
      <span className="whitespace-nowrap text-muted-foreground">{formatModelTypeLabel(getValue<string>())}</span>
    ),
  },
  {
    id: "context",
    accessorKey: "context_window",
    header: ({ column }) => (
      <SortableHeader column={column} align="right">
        Context
      </SortableHeader>
    ),
    cell: ({ getValue }) => (
      <span className="tabular-nums text-muted-foreground">{formatCompactTokens(getValue<number>())}</span>
    ),
    meta: { align: "right" },
  },
  {
    id: "input",
    accessorFn: (row) => row.pricing.input_per_million,
    header: ({ column }) => (
      <SortableHeader column={column} align="right">
        Input / 1M
      </SortableHeader>
    ),
    cell: ({ getValue }) => priceCell(getValue<number>()),
    meta: { align: "right" },
  },
  {
    id: "output",
    accessorFn: (row) => row.pricing.output_per_million,
    header: ({ column }) => (
      <SortableHeader column={column} align="right">
        Output / 1M
      </SortableHeader>
    ),
    cell: ({ getValue }) => priceCell(getValue<number>()),
    meta: { align: "right" },
  },
  {
    id: "cacheRead",
    accessorFn: (row) => row.pricing.cache_read_per_million ?? undefined,
    sortUndefined: "last",
    header: ({ column }) => (
      <SortableHeader column={column} align="right">
        Cache read
      </SortableHeader>
    ),
    cell: ({ getValue }) => priceCell(getValue<number | null>()),
    meta: { align: "right" },
  },
  {
    id: "cacheWrite",
    accessorFn: (row) => row.pricing.cache_creation_per_million ?? undefined,
    sortUndefined: "last",
    header: ({ column }) => (
      <SortableHeader column={column} align="right">
        Cache write
      </SortableHeader>
    ),
    cell: ({ getValue }) => priceCell(getValue<number | null>()),
    meta: { align: "right" },
  },
];

export function ExplorerView({ models }: { models: ModelRow[] }) {
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState("all");
  const [modelType, setModelType] = useState("chat");
  const [sorting, setSorting] = useState<SortingState>([{ id: "model", desc: false }]);

  const providers = useMemo(() => {
    const labels = new Map<string, string>();
    for (const model of models) {
      labels.set(model.provider, model.providerLabel);
    }
    return Array.from(labels.entries()).sort((left, right) => left[1].localeCompare(right[1], "en-US"));
  }, [models]);

  const modelTypes = useMemo(
    () => Array.from(new Set(models.map((model) => model.model_type))).sort(),
    [models],
  );


  const filtered = useMemo(() => {
    const lowered = query.trim().toLowerCase();
    return models.filter((model) => {
      if (provider !== "all" && model.provider !== provider) {
        return false;
      }
      if (modelType !== "all" && model.model_type !== modelType) {
        return false;
      }

      if (!lowered) {
        return true;
      }
      return (
        model.name.toLowerCase().includes(lowered) ||
        model.model_id.toLowerCase().includes(lowered) ||
        model.providerLabel.toLowerCase().includes(lowered) ||
        model.category.toLowerCase().includes(lowered)
      );
    });
  }, [modelType, models, provider, query]);

  const table = useReactTable({
    data: filtered,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 25 } },
  });

  const { pageIndex, pageSize } = table.getState().pagination;
  const firstRow = filtered.length === 0 ? 0 : pageIndex * pageSize + 1;
  const lastRow = Math.min(filtered.length, (pageIndex + 1) * pageSize);

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2 border-b p-4">
        <div className="relative min-w-56 flex-1 sm:max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search models, providers, ids…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="Search models"
          />
        </div>
        <Select value={provider} onValueChange={setProvider}>
          <SelectTrigger className="w-48" aria-label="Filter by provider">
            <SelectValue placeholder="Provider" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All providers</SelectItem>
            {providers.map(([slug, label]) => (
              <SelectItem key={slug} value={slug}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={modelType} onValueChange={setModelType}>
          <SelectTrigger className="w-44" aria-label="Filter by model type">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            {modelTypes.map((type) => (
              <SelectItem key={type} value={type}>
                {formatModelTypeLabel(type)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="ml-auto text-sm text-muted-foreground tabular-nums">
          {formatInteger(filtered.length)} models
        </span>
      </div>

      <div className="max-h-[36rem] overflow-auto">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  const align = header.column.columnDef.meta?.align;
                  return (
                    <TableHead key={header.id} className={cn(align === "right" && "text-right")}>
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </TableHead>
                  );
                })}
              </tr>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow key={row.id}>
                {row.getVisibleCells().map((cell) => {
                  const align = cell.column.columnDef.meta?.align;
                  return (
                    <TableCell key={cell.id} className={cn(align === "right" && "text-right")}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={columns.length}>
                  <div className="flex flex-col items-center gap-2 py-16 text-muted-foreground">
                    <SearchX className="h-6 w-6" />
                    <p className="m-0 text-sm">No models match the current filters.</p>
                  </div>
                </td>
              </tr>
            ) : null}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t p-3 px-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>Rows per page</span>
          <Select value={String(pageSize)} onValueChange={(value) => table.setPageSize(Number(value))}>
            <SelectTrigger className="h-8 w-[4.5rem]" aria-label="Rows per page">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PAGE_SIZES.map((size) => (
                <SelectItem key={size} value={String(size)}>
                  {size}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground tabular-nums">
            {formatInteger(firstRow)}–{formatInteger(lastRow)} of {formatInteger(filtered.length)}
          </span>
          <Button
            variant="outline"
            size="iconSm"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            aria-label="Previous page"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="iconSm"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            aria-label="Next page"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </Card>
  );
}

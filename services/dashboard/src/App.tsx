import { AlertCircle, ArrowLeftRight, Calculator, History, TableProperties, TrendingUp } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { CalculatorView } from "./components/calculator";
import { ChangelogView } from "./components/changelog";
import { buildModelOptions, CompareView } from "./components/compare";
import { ExplorerView } from "./components/explorer";
import { Footer } from "./components/footer";
import { Header } from "./components/header";
import { HistoryView } from "./components/history";
import { StatsRow } from "./components/stats";
import { Card } from "./components/ui/card";
import { Skeleton } from "./components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/tabs";
import {
  loadChangelogData,
  loadPricingData,
  normalizeModels,
  type ChangelogData,
  type ModelRow,
} from "./lib/data";
import { cn, formatInteger } from "./lib/utils";

const CYCLING_WORDS = ["AI agents", "chatbots", "copilots", "RAG pipelines", "batch jobs"];
const CYCLE_INTERVAL_MS = 2600;
const CYCLE_TRANSITION_MS = 300;

/**
 * Word carousel in the hero heading: the current word slides down and fades
 * out, then the next one takes its place. Holds still when the user prefers
 * reduced motion.
 */
function CyclingWord({ words }: { words: string[] }) {
  const [index, setIndex] = useState(0);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }
    const timer = setInterval(() => {
      setLeaving(true);
      setTimeout(() => {
        setIndex((current) => (current + 1) % words.length);
        setLeaving(false);
      }, CYCLE_TRANSITION_MS);
    }, CYCLE_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [words.length]);

  return (
    <span className="inline-block whitespace-nowrap font-light italic text-primary">
      <span
        className={cn(
          "inline-block transition-all duration-300 ease-in-out",
          leaving ? "translate-y-2 opacity-0" : "translate-y-0 opacity-100",
        )}
      >
        {words[index]}
      </span>
    </span>
  );
}

function App() {
  const [models, setModels] = useState<ModelRow[]>([]);
  const [changelog, setChangelog] = useState<ChangelogData | null>(null);
  const [generatedAt, setGeneratedAt] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [compareA, setCompareA] = useState("");
  const [compareB, setCompareB] = useState("");
  const [calculatorModel, setCalculatorModel] = useState("");

  useEffect(() => {
    Promise.all([loadPricingData(), loadChangelogData().catch(() => null)])
      .then(([pricingData, changelogData]) => {
        const entries = normalizeModels(pricingData);
        setModels(entries);
        setGeneratedAt(pricingData.generated_at);
        setChangelog(changelogData);

        // Seed pickers with well-known text models so Compare and Calculator
        // open with a meaningful example instead of an alphabetical artifact.
        // Accept the legacy "chat" type until the database adopts the
        // OpenRouter taxonomy everywhere.
        const chatModels = entries.filter(
          (model) =>
            (model.model_type === "text" || model.model_type === "chat") &&
            model.pricing.input_per_million > 0,
        );
        const findByPrefix = (prefix: string) =>
          chatModels.find((model) => model.model_id.startsWith(prefix) && model.category === "flagship")
            ?.model_id ?? chatModels.find((model) => model.model_id.startsWith(prefix))?.model_id;
        const first = findByPrefix("openai/") ?? chatModels[0]?.model_id ?? "";
        const second =
          findByPrefix("anthropic/") ??
          chatModels.find((model) => model.model_id !== first)?.model_id ??
          first;
        setCompareA(first);
        setCompareB(second);
        setCalculatorModel(first);
      })
      .catch((loadError: Error) => setError(loadError.message))
      .finally(() => setLoading(false));
  }, []);

  const providerCount = useMemo(() => new Set(models.map((model) => model.provider)).size, [models]);
  const modelOptions = useMemo(() => buildModelOptions(models), [models]);

  return (
    <div className="flex min-h-screen flex-col">
      <Header generatedAt={generatedAt} />

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 md:px-6">
        <div className="mb-8 flex flex-col gap-2">
          <h1 className="m-0 font-serif text-4xl font-normal leading-tight md:text-5xl">
            Token pricing for <CyclingWord words={CYCLING_WORDS} />
          </h1>
          <p className="m-0 max-w-2xl text-sm text-muted-foreground">
            Canonical input, output, and cache token rates
            {models.length > 0 ? ` for ${formatInteger(models.length)} AI models across ${formatInteger(providerCount)} providers` : ""}
            , synchronized from OpenRouter and LiteLLM every six hours.
          </p>
        </div>

        {error ? (
          <Card className="mb-6 flex items-center gap-3 border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>
              Could not load the pricing database: {error}. Retry once the canonical data endpoint is reachable.
            </span>
          </Card>
        ) : null}

        <div className="flex flex-col gap-6">
          <StatsRow models={models} generatedAt={generatedAt} loading={loading} />

          <Tabs defaultValue="explorer">
            <TabsList className="mb-4">
              <TabsTrigger value="explorer">
                <TableProperties className="h-3.5 w-3.5" />
                Explorer
              </TabsTrigger>
              <TabsTrigger value="compare">
                <ArrowLeftRight className="h-3.5 w-3.5" />
                Compare
              </TabsTrigger>
              <TabsTrigger value="calculator">
                <Calculator className="h-3.5 w-3.5" />
                Calculator
              </TabsTrigger>
              <TabsTrigger value="history">
                <TrendingUp className="h-3.5 w-3.5" />
                History
              </TabsTrigger>
              <TabsTrigger value="changelog">
                <History className="h-3.5 w-3.5" />
                Changelog
              </TabsTrigger>
            </TabsList>

            {loading ? (
              <Card className="p-4">
                <Skeleton className="mb-4 h-9 w-full max-w-sm" />
                <div className="flex flex-col gap-3">
                  {Array.from({ length: 8 }, (_, index) => (
                    <Skeleton key={index} className="h-9 w-full" />
                  ))}
                </div>
              </Card>
            ) : (
              <>
                <TabsContent value="explorer">
                  <ExplorerView models={models} />
                </TabsContent>
                <TabsContent value="compare">
                  <CompareView
                    models={models}
                    options={modelOptions}
                    modelA={compareA}
                    modelB={compareB}
                    onChangeA={setCompareA}
                    onChangeB={setCompareB}
                  />
                </TabsContent>
                <TabsContent value="calculator">
                  <CalculatorView
                    models={models}
                    options={modelOptions}
                    selected={calculatorModel}
                    onSelect={setCalculatorModel}
                  />
                </TabsContent>
                <TabsContent value="history">
                  <HistoryView
                    models={models}
                    options={modelOptions}
                    modelA={compareA}
                    modelB={compareB}
                    onChangeA={setCompareA}
                    onChangeB={setCompareB}
                  />
                </TabsContent>
                <TabsContent value="changelog">
                  <ChangelogView changelog={changelog} />
                </TabsContent>
              </>
            )}
          </Tabs>
        </div>
      </main>

      <Footer />
    </div>
  );
}

export default App;

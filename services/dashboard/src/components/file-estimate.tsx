import { AlertCircle, Info, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { estimateTokens, type TokenEstimate } from "../lib/estimate";
import { extractText, supportedFormats } from "../lib/extract";
import { formatInteger } from "../lib/utils";
import { Button } from "./ui/button";

interface Result {
  fileName: string;
  pages?: number;
  estimate: TokenEstimate;
}

/**
 * Upload a document and turn it into an estimated input-token count.
 *
 * The number handed to `onEstimate` is an estimate and is labelled as such
 * everywhere it is shown: provider tokenizers differ, so a single exact figure
 * would be wrong for every model but one.
 */
export function FileEstimate({ onEstimate }: { onEstimate: (tokens: number) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);

  const handleFile = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      const extracted = await extractText(file);
      const estimate = estimateTokens(extracted.text);
      setResult({ fileName: file.name, pages: extracted.pages, estimate });
      onEstimate(estimate.tokens);
    } catch (cause) {
      setResult(null);
      setError(cause instanceof Error ? cause.message : "Could not read this file.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-2 rounded-md border border-dashed p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-sm font-medium">Estimate from a file</div>
          <div className="text-xs text-muted-foreground">
            Fills the input tokens field. {supportedFormats()}
          </div>
        </div>
        <Button variant="outline" size="sm" disabled={busy} onClick={() => inputRef.current?.click()}>
          <Upload className="h-3.5 w-3.5" />
          {busy ? "Reading…" : "Choose file"}
        </Button>
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          aria-label="File to estimate"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) {
              void handleFile(file);
            }
          }}
        />
      </div>

      {result ? (
        <div className="flex flex-col gap-1 border-t pt-2 text-xs">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="truncate font-medium">{result.fileName}</span>
            <span className="tabular-nums">
              ~{formatInteger(result.estimate.tokens)} tokens
              <span className="text-muted-foreground">
                {" "}
                ({formatInteger(result.estimate.low)}–{formatInteger(result.estimate.high)})
              </span>
            </span>
          </div>
          <p className="m-0 flex items-start gap-2 text-muted-foreground">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>
              Estimate, not a count — {result.estimate.method}. Tokenizers differ across providers, so treat
              this as an order of magnitude.
              {result.pages ? ` Read ${formatInteger(result.pages)} page${result.pages === 1 ? "" : "s"}.` : ""}
            </span>
          </p>
        </div>
      ) : null}

      {error ? (
        <p className="m-0 flex items-start gap-2 border-t pt-2 text-xs text-warning">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          {error}
        </p>
      ) : null}
    </div>
  );
}

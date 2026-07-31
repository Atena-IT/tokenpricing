/**
 * Text extraction from uploaded files.
 *
 * Plain-text formats are read directly. PDF is handled by pdfjs-dist, loaded
 * through a dynamic import so that the parser lands in its own chunk and is
 * only downloaded by users who actually open a PDF — the production bundle
 * already sits above Vite's 500 kB warning threshold.
 */

export interface ExtractedText {
  /** The extracted plain text. */
  text: string;
  /** How the text was obtained, for display alongside the estimate. */
  source: "text" | "pdf";
  /** Page count, when the format has pages. */
  pages?: number;
}

/** Extensions read verbatim as UTF-8 text. */
const TEXT_EXTENSIONS = [
  "txt",
  "md",
  "markdown",
  "csv",
  "tsv",
  "json",
  "jsonl",
  "yaml",
  "yml",
  "xml",
  "html",
  "css",
  "js",
  "jsx",
  "ts",
  "tsx",
  "py",
  "rs",
  "go",
  "java",
  "sql",
  "sh",
  "log",
] as const;

const SUPPORTED = [...TEXT_EXTENSIONS, "pdf"];

function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "" : name.slice(dot + 1).toLowerCase();
}

export function isSupported(fileName: string): boolean {
  return SUPPORTED.includes(extensionOf(fileName));
}

/** Human-readable list of what can be uploaded, for UI hints and errors. */
export function supportedFormats(): string {
  return SUPPORTED.map((extension) => `.${extension}`).join(", ");
}

async function extractPdf(file: File): Promise<ExtractedText> {
  const pdfjs = await import("pdfjs-dist");
  const worker = await import("pdfjs-dist/build/pdf.worker.mjs?url");
  pdfjs.GlobalWorkerOptions.workerSrc = worker.default;

  const task = pdfjs.getDocument({ data: await file.arrayBuffer() });
  const document = await task.promise;
  const pages: string[] = [];

  try {
    for (let pageNumber = 1; pageNumber <= document.numPages; pageNumber += 1) {
      const page = await document.getPage(pageNumber);
      const content = await page.getTextContent();
      pages.push(content.items.map((item) => ("str" in item ? item.str : "")).join(" "));
    }
    return { text: pages.join("\n\n"), source: "pdf", pages: document.numPages };
  } finally {
    // Releases the worker; without this every upload leaks one.
    await task.destroy();
  }
}

/**
 * Read the text content of an uploaded file.
 *
 * @throws Error with a message naming the supported formats when the extension
 * is not one this dashboard can read.
 */
export async function extractText(file: File): Promise<ExtractedText> {
  const extension = extensionOf(file.name);

  if (extension === "pdf") {
    return extractPdf(file);
  }

  if (!isSupported(file.name)) {
    throw new Error(
      `Cannot read ".${extension || file.name}". Supported formats: ${supportedFormats()}.`,
    );
  }

  return { text: await file.text(), source: "text" };
}

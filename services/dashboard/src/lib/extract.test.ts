import { describe, expect, it } from "vitest";

import { extractText, isSupported, supportedFormats } from "./extract";

function fileOf(name: string, contents = "hello world"): File {
  return new File([contents], name, { type: "text/plain" });
}

describe("isSupported", () => {
  it("accepts plain-text formats regardless of case", () => {
    expect(isSupported("notes.md")).toBe(true);
    expect(isSupported("NOTES.MD")).toBe(true);
    expect(isSupported("data.CSV")).toBe(true);
  });

  it("accepts pdf", () => {
    expect(isSupported("book.pdf")).toBe(true);
  });

  it("rejects formats it cannot read", () => {
    expect(isSupported("report.docx")).toBe(false);
    expect(isSupported("archive.zip")).toBe(false);
    expect(isSupported("noextension")).toBe(false);
  });
});

describe("extractText", () => {
  it("reads a plain-text file verbatim", async () => {
    const result = await extractText(fileOf("chapter.txt", "Once upon a time"));
    expect(result).toEqual({ text: "Once upon a time", source: "text" });
  });

  it("reads markdown and source files too", async () => {
    expect((await extractText(fileOf("readme.md", "# Title"))).text).toBe("# Title");
    expect((await extractText(fileOf("main.py", "print(1)"))).text).toBe("print(1)");
  });

  it("handles an empty file without failing", async () => {
    expect((await extractText(fileOf("empty.txt", ""))).text).toBe("");
  });

  it("rejects unsupported formats with a message naming what it can read", async () => {
    await expect(extractText(fileOf("report.docx"))).rejects.toThrow(/docx/);
    await expect(extractText(fileOf("report.docx"))).rejects.toThrow(/\.pdf/);
  });
});

describe("supportedFormats", () => {
  it("lists extensions with a leading dot", () => {
    expect(supportedFormats()).toContain(".txt");
    expect(supportedFormats()).toContain(".pdf");
  });
});

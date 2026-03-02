import { afterEach, describe, expect, it, vi } from "vitest";
import { clearRatesCache, getUsdRate, getUsdRates } from "../src/currency.js";

// Mock global fetch
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

const SAMPLE_RATES = {
  usd: {
    eur: 0.92,
    gbp: 0.79,
    jpy: 149.5,
    cny: 7.24,
  },
};

describe("getUsdRates", () => {
  afterEach(() => {
    clearRatesCache();
    mockFetch.mockReset();
  });

  it("should fetch and return uppercased rates", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(SAMPLE_RATES),
    });

    const rates = await getUsdRates();
    expect(rates.EUR).toBe(0.92);
    expect(rates.GBP).toBe(0.79);
    expect(rates.JPY).toBe(149.5);
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("should cache rates on subsequent calls", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(SAMPLE_RATES),
    });

    await getUsdRates();
    await getUsdRates();
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("should throw on non-200 response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 503,
      statusText: "Service Unavailable",
    });

    await expect(getUsdRates()).rejects.toThrow("Failed to fetch USD rates");
  });
});

describe("getUsdRate", () => {
  afterEach(() => {
    clearRatesCache();
    mockFetch.mockReset();
  });

  it("should return 1 for USD without fetching", async () => {
    const rate = await getUsdRate("USD");
    expect(rate).toBe(1);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("should return 1 for lowercase usd", async () => {
    const rate = await getUsdRate("usd");
    expect(rate).toBe(1);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("should return rate for known currency", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(SAMPLE_RATES),
    });

    const rate = await getUsdRate("EUR");
    expect(rate).toBe(0.92);
  });

  it("should throw for unknown currency with suggestion", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(SAMPLE_RATES),
    });

    await expect(getUsdRate("ERU")).rejects.toThrow(/Did you mean/);
  });

  it("should throw for completely unknown currency", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(SAMPLE_RATES),
    });

    await expect(getUsdRate("XYZ")).rejects.toThrow(
      "Unsupported currency: XYZ",
    );
  });
});

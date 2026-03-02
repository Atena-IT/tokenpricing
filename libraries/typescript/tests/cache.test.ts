import { describe, expect, it, vi } from "vitest";
import { TtlCache } from "../src/cache.js";

describe("TtlCache", () => {
  it("should call loader on first access", async () => {
    const loader = vi.fn().mockResolvedValue("hello");
    const cache = new TtlCache(1000, loader);

    const result = await cache.get();
    expect(result).toBe("hello");
    expect(loader).toHaveBeenCalledTimes(1);
  });

  it("should return cached value within TTL", async () => {
    let now = 0;
    const loader = vi.fn().mockResolvedValue("cached");
    const cache = new TtlCache(1000, loader, () => now);

    await cache.get();
    now = 500; // Still within TTL
    const result = await cache.get();

    expect(result).toBe("cached");
    expect(loader).toHaveBeenCalledTimes(1);
  });

  it("should refresh after TTL expires", async () => {
    let now = 0;
    const loader = vi
      .fn()
      .mockResolvedValueOnce("first")
      .mockResolvedValueOnce("second");
    const cache = new TtlCache(1000, loader, () => now);

    const first = await cache.get();
    expect(first).toBe("first");

    now = 1001; // Past TTL
    const second = await cache.get();
    expect(second).toBe("second");
    expect(loader).toHaveBeenCalledTimes(2);
  });

  it("should force refresh when requested", async () => {
    const loader = vi
      .fn()
      .mockResolvedValueOnce("first")
      .mockResolvedValueOnce("forced");
    const cache = new TtlCache(10000, loader);

    await cache.get();
    const result = await cache.get(true);
    expect(result).toBe("forced");
    expect(loader).toHaveBeenCalledTimes(2);
  });

  it("should clear the cache", async () => {
    const loader = vi
      .fn()
      .mockResolvedValueOnce("before")
      .mockResolvedValueOnce("after");
    const cache = new TtlCache(10000, loader);

    await cache.get();
    cache.clear();
    const result = await cache.get();

    expect(result).toBe("after");
    expect(loader).toHaveBeenCalledTimes(2);
  });

  it("should deduplicate concurrent calls", async () => {
    const loader = vi.fn().mockResolvedValue("deduped");
    const cache = new TtlCache(1000, loader);

    const [a, b, c] = await Promise.all([
      cache.get(),
      cache.get(),
      cache.get(),
    ]);

    expect(a).toBe("deduped");
    expect(b).toBe("deduped");
    expect(c).toBe("deduped");
    expect(loader).toHaveBeenCalledTimes(1);
  });

  it("should propagate loader errors", async () => {
    const loader = vi.fn().mockRejectedValue(new Error("fail"));
    const cache = new TtlCache(1000, loader);

    await expect(cache.get()).rejects.toThrow("fail");
  });

  it("should retry after a failed load", async () => {
    const loader = vi
      .fn()
      .mockRejectedValueOnce(new Error("fail"))
      .mockResolvedValueOnce("recovered");
    const cache = new TtlCache(1000, loader);

    await expect(cache.get()).rejects.toThrow("fail");
    const result = await cache.get();
    expect(result).toBe("recovered");
    expect(loader).toHaveBeenCalledTimes(2);
  });
});

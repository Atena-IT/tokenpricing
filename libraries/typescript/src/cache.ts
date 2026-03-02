/**
 * Generic single-entry TTL cache.
 *
 * Stores one value with a time-to-live. After TTL expires,
 * the next access triggers a fresh fetch via the provided loader.
 */
export class TtlCache<T> {
  private value: T | undefined = undefined;
  private expiresAt = 0;
  private pending: Promise<T> | undefined = undefined;

  constructor(
    private readonly ttlMs: number,
    private readonly loader: () => Promise<T>,
    private readonly now: () => number = Date.now,
  ) {}

  async get(forceRefresh = false): Promise<T> {
    if (
      !forceRefresh &&
      this.value !== undefined &&
      this.now() < this.expiresAt
    ) {
      return this.value;
    }

    // Deduplicate concurrent calls
    if (this.pending) {
      return this.pending;
    }

    this.pending = this.loader()
      .then((result) => {
        this.value = result;
        this.expiresAt = this.now() + this.ttlMs;
        this.pending = undefined;
        return result;
      })
      .catch((err) => {
        this.pending = undefined;
        throw err;
      });

    return this.pending;
  }

  clear(): void {
    this.value = undefined;
    this.expiresAt = 0;
    this.pending = undefined;
  }
}

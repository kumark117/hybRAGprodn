# LLM 429 and provider quotas

HTTP 429 is retryable. It is not a bug in your prompt.

## What 429 means

The vendor is rate-limiting **your API key** (RPM/TPM). Retrying immediately without backoff guarantees more 429s.

## Stacked controls

1. **Retry + jitter** — survive short bursts
2. **Concurrency limiter** — `MAX_LLM_CONCURRENCY` caps in-flight generations
3. **Rate limiter** — per user / per tenant 429 from *our* API before we even call OpenAI
4. **Fallback model** — different quota pool or cheaper model after retry budget

Rate limiting ≠ concurrency limiting.

- Rate: 60 queries / minute / user
- Concurrency: at most 8 LLM calls at once on this process

## Log pattern

```
WARN  LLM    operation_failed status=429
INFO  RETRY  delay_seconds=1.14
OK    LLM    fallback provider succeeded
```

If fallback is the **same** model name, you did not fail over; you only retried. Configure `OPENAI_FALLBACK_MODEL` to a real second model in production.

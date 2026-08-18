# Rate limit 429 from our API vs vendor 429

Users confuse them.

## Our 429 (`RATE_LIMITED`)

Redis (or in-memory) sliding window: `RATE_LIMIT_PER_USER_PER_MINUTE`, `RATE_LIMIT_PER_TENANT_PER_MINUTE`. Protects **us** from one noisy tenant.

## Vendor 429

OpenAI/Pinecone quota. Logged as provider errors, retried with jitter, may failover.

If you raise our limiter but not `MAX_LLM_CONCURRENCY`, a tenant can still stampede the vendor from a single burst inside the minute window.

Return JSON:

```
{"error":{"code":"RATE_LIMITED","message":"Too many requests","request_id":"req-..."}}
```

Never attach the user’s token in that body.

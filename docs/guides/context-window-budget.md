# Context window budget

The LLM does not get “all good chunks.” `ContextBuilder` enforces:

- `MAX_CONTEXT_TOKENS` (approx chars/4 in this app)
- `MAX_CHUNKS_PER_SOURCE` so one giant PDF cannot drown other files

If you index an entire monorepo and ask a narrow question, you will still only stuff a handful of chunks. That is intentional.

## Observable fields

```
context_candidates=27
context_selected=6
context_tokens=4218
documents_represented=4
```

If `documents_represented=1` always, diversity cap may be too high for that source or retrieval is stuck on one file.

## Truncation

A single oversized chunk is truncated rather than skipped entirely, so at least some evidence remains.

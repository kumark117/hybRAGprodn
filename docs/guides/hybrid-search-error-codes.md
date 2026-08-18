# Why hybrid search catches error codes

Dense embeddings are weak on rare tokens. Examples that bit us:

| Query | Vector-only | BM25-only | Hybrid |
| --- | --- | --- | --- |
| E-2044 stale lexical index | miss / wrong doc | hit INC-2044 | hit |
| HTTP 429 | sometimes | hit llm-429-quotas | hit |
| SKU RETRY-POLICY-v3 | miss | hit | hit |
| “how do we back off when the vendor is slow” | hit retry runbook | weaker | hit |

RRF formula (k=60):

```
RRF(d) = Σ  1 / (k + rank_i(d))
```

Do not add raw BM25 scores to cosine similarities. They are different units.

If product asks “why did we build two retrievers,” this table is the answer.

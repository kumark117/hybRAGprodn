# Graceful degradation catalog

| Failure | User-visible mode | Still enforced |
| --- | --- | --- |
| Pinecone timeout after retries | `bm25_only`, `degraded_mode=true` | tenant JWT + BM25 tenant corpus |
| BM25 process error | `vector_only` | Pinecone tenant filter |
| Reranker down | RRF order | same |
| Redis down, fail-open | extra latency, no cache | same |
| Primary LLM dead | fallback model | same |
| Both retrievers dead | empty context, honest “not enough evidence” | same |

Never degrade:

- authentication
- tenant match
- store-level tenant filters

Degraded answers can still be wrong. Show `degraded_mode` in the UI so operators do not treat them as full hybrid quality.

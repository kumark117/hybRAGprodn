# Embedding dimension mismatch

Pinecone index created at dimension 1536. App switched to a 3072-dim model (or the hash embedder at 64 dims in fake mode). Upserts fail or queries return empty.

## Rule

`EMBEDDING_MODEL_VERSION` belongs in cache keys **and** you must rebuild the vector index when the model (or dimension) changes. Old vectors are not comparable.

## Fake vs prod

`USE_FAKE_PROVIDERS=true` uses 64-d hash embeddings and an in-memory store. Turning fakes off without creating a matching Pinecone index is a silent empty-retrieval bug.

Always bump `INDEX_VERSION` when you re-embed the corpus so exact cache does not serve answers grounded on the old index.

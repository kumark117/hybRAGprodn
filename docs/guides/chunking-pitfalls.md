# Chunking mistakes that wreck retrieval

## Too large (`CHUNK_SIZE` 4000+)

Each Pinecone match dumps a wall of text. Context builder hits `MAX_CONTEXT_TOKENS` after two chunks. Citations look right; the LLM never saw the paragraph with the actual timeout numbers.

## Too small (`CHUNK_SIZE` 40)

The sentence “Do not retry 401” splits from “Do not retry 403.” BM25 still finds tokens; the model cannot form a policy.

## Overlap

`CHUNK_OVERLAP` exists so sentences on a boundary appear in two chunks. Zero overlap causes “the number is in the other chunk” misses. Huge overlap duplicates vectors and wastes quota.

## Idempotency

Chunk IDs hash `tenant + document_id + version + index + normalized text`. Re-indexing the same file must **replace**, not duplicate. Duplicate chunks pollute RRF (same text, two IDs) and steal context slots.

See `backend/app/indexing/ids.py` and `chunker.py`.

# Duplicate chunks after re-index (INC-6201)

A nightly job posted the same `document_id` without deleting old vectors. Deterministic IDs should have overwritten. A bug used `uuid4()` for chunk IDs “to be extra unique.” Pinecone accumulated 14 copies. Context builder picked near-duplicates from one PDF. Other sources vanished.

## Fix

Use `make_chunk_id(tenant, document, version, index, normalized_text)`.

Indexing service deletes the document from vector + BM25 **before** upsert so version changes that alter chunk boundaries cannot leave orphans.

If you change `document_version`, old IDs will not collide — you must still delete the previous version’s vectors.

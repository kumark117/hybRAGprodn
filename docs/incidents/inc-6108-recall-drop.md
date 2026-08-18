# Recall@K dropped after a chunker change (INC-6108)

Offline eval (`python -m app.evaluation.run`) fell from Recall@5 1.00 to 0.40 after increasing overlap and accidentally shrinking `CHUNK_SIZE` to 64.

## Why eval exists

Online “it looks fine” misses silent retrieval regressions. Tiny datasets still catch “we no longer return retry-guide for retry questions.”

## Metrics

- Recall@K — did the right doc appear in top K?
- Precision@K — how much junk in top K?
- MRR — rank of first relevant
- nDCG — position-sensitive

Re-run eval in CI when you touch `chunker.py`, `fusion.py`, `RRF_K`, or embedding model.

The bundled dataset is tiny on purpose. Grow `backend/app/evaluation/dataset.json` with real questions before you trust the numbers.

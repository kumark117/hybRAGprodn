# Hot document domination

One architecture.pdf is 80 pages. Hybrid retrieval returns 20 chunks, 18 from that PDF. Other runbooks never enter context. Answers ignore INC-2044 even when the user asked about E-2044.

`MAX_CHUNKS_PER_SOURCE` exists to stop this. If it is 99, you effectively turned it off.

Also consider **source diversification** at RRF time (MMR / round-robin by `document_id`). This app diversifies in the context builder, not in RRF.

Product-wise: split mega-PDFs at ingest (per chapter) so `source` metadata is finer than one filename.

# Indexing huge folders

`python -m app.cli index-folder ..\docs` walks text files and POSTs each document to the live API.

## Production issues

- **Timeouts**: each file is a full embed+upsert. A 5k-file corpus will take a while and can 429 the embedder. Batch embeddings (already used inside one document) do not batch **across** files in the CLI.
- **Max size**: files over `MAX_DOCUMENT_SIZE` / `--max-bytes` are skipped. Users think “it indexed the folder” but the 2MB runbook never landed.
- **Binary skip**: null bytes → skip. PDFs are **not** parsed here. Convert PDF to markdown first or you will retrieve nothing from “the PDF folder.”
- **Same process**: the CLI must hit the **running** Uvicorn. A second in-process index does not update the server’s RAM BM25.

For PDFs/Office in real systems, use a parser worker (Unstructured, Apache Tika) and then the same `/api/v1/index` contract.

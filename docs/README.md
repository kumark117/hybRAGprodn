# Production corpus

These notes are meant to be **indexed** and queried through the RAG console.

Index them (backend must be running):

```powershell
cd backend
python -m app.cli index-folder ..\docs
```

Then ask questions such as:

- How does the system handle retries?
- What happened in incident INC-4291?
- Why did BM25 miss error code E-2044?
- What is a cache stampede?
- Why must we not put request_id on Prometheus labels?

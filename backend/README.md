# Hybrid RAG backend

Local development defaults to fake LLM/embeddings so you can study the pipeline
without paid API calls. Set `USE_FAKE_PROVIDERS=false` plus provider keys for
Pinecone and OpenAI-compatible APIs.

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

## Test

```bash
pytest
```

## Evaluate retrieval

```bash
python -m app.evaluation.run
```

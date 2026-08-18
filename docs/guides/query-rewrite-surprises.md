# Query rewrite surprises

Conversational follow-up: “What about its retry policy?” needs a standalone rewrite (“What is the system retry policy for HTTP 429?”).

Bad rewrite: the LLM “answers” instead of rewriting, and you embed a long paragraph. Retrieval goes off the rails.

This app only rewrites when pronouns / “what about” patterns match (`REWRITE_ENABLED`). Failures fall back to the original query.

Do not log the full rewritten question at INFO. Debug mode (authorized roles) may show it.

If rewrite is slow, it sits on the critical path before embed — it adds to TTFT end-to-end even though TTFT metric starts at the LLM call.

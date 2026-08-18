# Liveness vs readiness probes

Kubernetes (and any load balancer) needs both.

## `/health/live`

The process is running. Do **not** fail liveness because Redis is down or Pinecone timed out. That kills pods during a dependency blip and causes a restart storm.

## `/health/ready`

Safe to receive traffic. BM25 (or equivalent lexical) should be up. Vector may be `degraded`. Redis may be `optional_unavailable` when fail-open.

## INC-5002

An engineer wired Redis ping into **liveness**. Redis maintenance = all RAG pods killed = longer outage than the cache miss would have been.

Remember: optional dependencies belong on ready/degraded, not live.

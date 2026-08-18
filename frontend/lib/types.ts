export type LogLevel =
  | "DEBUG"
  | "INFO"
  | "WARN"
  | "ERROR"
  | "START"
  | "OK"
  | "MISS"
  | "HIT"
  | "DONE";

export interface LogEvent {
  requestId: string;
  timestamp: string;
  level: LogLevel;
  stage: string;
  event: string;
  message: string;
  durationMs?: number;
  metadata?: Record<string, unknown>;
}

export interface TokenEvent {
  requestId: string;
  text: string;
}

export interface CitationEvent {
  requestId: string;
  citation_id?: number;
  document_id?: string;
  chunk_id?: string;
  source?: string;
  retrieval_score?: number;
  rrf_score?: number;
  reranker_score?: number;
  text_preview?: string;
}

export interface RAGMetadata {
  cache_hit: boolean;
  fallback_used: boolean;
  degraded_mode: boolean;
  retrieval_mode: "hybrid" | "vector_only" | "bm25_only" | "none";
  candidate_count: number;
  context_chunk_count: number;
  time_to_first_token_ms?: number | null;
  latency_ms: number;
  llm_model?: string | null;
  rewritten_query?: string | null;
  timings?: Record<string, number>;
  retry_count?: number;
  trace_id?: string | null;
}

export interface Source {
  citation_id: number;
  document_id: string;
  chunk_id: string;
  source: string;
  retrieval_score?: number | null;
  rrf_score?: number | null;
  reranker_score?: number | null;
  text_preview?: string | null;
}

export interface QueryRequest {
  query: string;
  tenant_id: string;
  top_k?: number;
  filters?: Record<string, unknown>;
  use_cache?: boolean;
  debug?: boolean;
}

export interface QueryResponse {
  request_id: string;
  trace_id?: string | null;
  answer: string;
  sources: Source[];
  metadata: RAGMetadata;
  debug?: Record<string, unknown> | null;
}

export interface IndexRequest {
  document_id: string;
  tenant_id: string;
  text: string;
  metadata?: Record<string, unknown>;
  document_version?: string;
}

export interface IndexResult {
  request_id: string;
  document_id: string;
  chunks_created: number;
  vectors_indexed: number;
  bm25_documents_indexed: number;
  status: string;
  timings?: Record<string, number>;
}

export interface DoneEvent {
  requestId: string;
  latencyMs: number;
  retrievalMode: string;
  cacheHit?: boolean;
  answer?: string;
}

export interface ErrorEvent {
  requestId: string;
  code: string;
  message: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  tenant_id: string;
  role: string;
  expires_in_minutes: number;
}

export type SSEHandler = {
  onLog?: (event: LogEvent) => void;
  onToken?: (event: TokenEvent) => void;
  onCitation?: (event: CitationEvent) => void;
  onMetadata?: (metadata: RAGMetadata) => void;
  onError?: (event: ErrorEvent) => void;
  onDone?: (event: DoneEvent) => void;
};

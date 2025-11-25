// TypeScript types matching the retrieval API schema

export interface Query {
    query_id: string;
    query_text: string;
    top_k: number;
}

export interface RetrievalRequest {
    mode: "lexical" | "vector" | "hybrid";
    queries: Query[];
}

export interface SegmentMetadata {
    title: string;
    url: string;
    headings: string[];
    extras: Record<string, string | number | boolean>;
}

export interface ProvenanceInfo {
    index_kind: string;
    dataset_version: string;
    chunking_config_hash: string;
}

export interface RetrievedSegment {
    segment_id: string;
    content: string;
    score: number;
    metadata: SegmentMetadata;
    provenance: ProvenanceInfo;
}

export interface RetrievalDiagnostics {
    latency_ms: number;
    config_hash: string;
    index_versions: Record<string, string>;
    warnings: string[];
}

export interface QueryResult {
    query_id: string;
    segments: RetrievedSegment[];
    diagnostics: RetrievalDiagnostics;
}

export interface RetrievalResponse {
    schema_version: string;
    dataset_version: string;
    config_hash: string;
    results: QueryResult[];
}

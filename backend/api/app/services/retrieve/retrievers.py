import requests
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from dataclasses import dataclass

@dataclass
class SearchResult:
    doc_id: str
    score: float
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class SolrRetriever:
    def __init__(self, base_url: str, core: str):
        self.base_url = base_url
        self.core = core
        self.search_url = f"{base_url}/{core}/select"

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        try:
            params = {
                'q': query,
                'rows': limit,
                'wt': 'json',
                'fl': 'id,score,body' # Assuming 'body' is the content field
            }
            response = requests.get(self.search_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for doc in data.get('response', {}).get('docs', []):
                results.append(SearchResult(
                    doc_id=str(doc['id']),
                    score=float(doc.get('score', 0.0)),
                    content=doc.get('body'),
                    metadata=doc
                ))
            return results
        except Exception as e:
            print(f"Solr search error: {e}")
            return []

class QdrantRetriever:
    def __init__(self, host: str, port: int, collection_name: str, api_key: Optional[str] = None):
        self.client = QdrantClient(host=host, port=port, api_key=api_key, https=False)
        self.collection_name = collection_name

    def search(self, vector: List[float], limit: int = 10) -> List[SearchResult]:
        try:
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=limit
            )
            
            results = []
            for hit in search_result:
                results.append(SearchResult(
                    doc_id=str(hit.id), # Qdrant uses 'id' or 'payload.id'? Usually 'id' is the point ID.
                    score=hit.score,
                    content=hit.payload.get('body') if hit.payload else None,
                    metadata=hit.payload
                ))
            return results
        except Exception as e:
            print(f"Qdrant search error: {e}")
            return []

class HybridRetriever:
    def __init__(self, solr_retriever: SolrRetriever, qdrant_retriever: QdrantRetriever):
        self.solr = solr_retriever
        self.qdrant = qdrant_retriever

    def search(self, query: str, vector: List[float], limit: int = 10, alpha: float = 0.5) -> List[SearchResult]:
        """
        Simple hybrid search combining results.
        Alpha controls the weight: 1.0 = pure vector, 0.0 = pure lexical (if we were doing linear combination).
        Here we'll use Reciprocal Rank Fusion (RRF) as it's robust.
        """
        lexical_results = self.solr.search(query, limit=limit * 2)
        vector_results = self.qdrant.search(vector, limit=limit * 2)
        
        return self.rrf(lexical_results, vector_results, limit=limit)

    def rrf(self, list1: List[SearchResult], list2: List[SearchResult], limit: int = 10, k: int = 60) -> List[SearchResult]:
        """
        Reciprocal Rank Fusion.
        """
        scores = {}
        
        # Helper to process a list
        def process_list(results):
            for rank, result in enumerate(results):
                if result.doc_id not in scores:
                    scores[result.doc_id] = {'score': 0.0, 'doc': result}
                scores[result.doc_id]['score'] += 1 / (k + rank + 1)

        process_list(list1)
        process_list(list2)
        
        # Sort by accumulated score
        sorted_docs = sorted(scores.values(), key=lambda x: x['score'], reverse=True)
        
        final_results = []
        for item in sorted_docs[:limit]:
            # We construct a new SearchResult with the fused score
            original_doc = item['doc']
            final_results.append(SearchResult(
                doc_id=original_doc.doc_id,
                score=item['score'],
                content=original_doc.content,
                metadata=original_doc.metadata
            ))
            
        return final_results

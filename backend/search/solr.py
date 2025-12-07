"""Solr indexing operations."""

import requests
from tqdm import tqdm


class SolrIndexer:
    """Solr indexing operations."""
    
    def __init__(self, base_url: str, core: str, timeout: int = 30):
        self.base_url = base_url
        self.core = core
        self.timeout = timeout
        self.update_url = f"{base_url}/{core}/update/json/docs"
        self.commit_url = f"{base_url}/{core}/update"
    
    def index(self, documents: list[dict], batch_size: int = 500) -> int:
        """Index documents in batches."""
        if not documents:
            return 0
        
        indexed = 0
        with tqdm(total=len(documents), desc="Indexing", unit="docs") as pbar:
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                try:
                    requests.post(
                        self.update_url,
                        json=batch,
                        params={'commit': 'false'},
                        headers={'Content-Type': 'application/json'},
                        timeout=self.timeout
                    ).raise_for_status()
                    indexed += len(batch)
                    pbar.update(len(batch))
                except requests.exceptions.RequestException as e:
                    pbar.write(f"Error: {str(e)[:80]}")
        try:
            requests.post(
                self.commit_url,
                params={'commit': 'true'},
                headers={'Content-Type': 'application/json'},
                timeout=self.timeout
            ).raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Commit error: {e}")
        
        return indexed
    
    def count(self) -> int:
        """Get document count in core."""
        try:
            resp = requests.get(
                f"{self.base_url}/{self.core}/select",
                params={'q': '*:*', 'rows': 0, 'wt': 'json'},
                timeout=self.timeout
            )
            resp.raise_for_status()
            return resp.json()['response']['numFound']
        except requests.exceptions.RequestException:
            return -1
    
    def delete_all(self) -> bool:
        """Delete all documents from the core."""
        try:
            requests.post(
                self.commit_url,
                json={'delete': {'query': '*:*'}},
                params={'commit': 'true'},
                headers={'Content-Type': 'application/json'},
                timeout=self.timeout
            ).raise_for_status()
            return True
        except requests.exceptions.RequestException:
            return False

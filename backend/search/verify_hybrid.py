import os
import sys
import time
from ssh_utils import SSHTunnelManager
from retrievers import SolrRetriever, QdrantRetriever, HybridRetriever
from db import Database

# Mock vector for testing - in real usage this would come from an embedding model
def get_mock_vector(dim=768):
    return [0.1] * dim

def main():
    print("Starting Hybrid Retrieval Verification...")
    
    # Check env vars
    required_vars = ["SSH_HOST", "SSH_USER"]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}")
        print("Please set SSH_HOST, SSH_USER (and SSH_KEY_PATH or SSH_PASSWORD) before running.")
        sys.exit(1)

    try:
        with SSHTunnelManager() as tunnel:
            ports = tunnel.local_ports
            print(f"Tunnel established. Ports: {ports}")
            
            # 1. Verify DB Connection
            print("\n[1] Verifying Database Connection...")
            db_config = {
                'host': 'localhost',
                'port': ports['db'],
                'database': 'postgres', # Default, might need env var
                'user': 'postgres',     # Default, might need env var
                'password': 'password'  # Default, might need env var
            }
            # Allow overriding DB creds via env
            if os.getenv("DB_NAME"): db_config['database'] = os.getenv("DB_NAME")
            if os.getenv("DB_USER"): db_config['user'] = os.getenv("DB_USER")
            if os.getenv("DB_PASSWORD"): db_config['password'] = os.getenv("DB_PASSWORD")
            
            try:
                db = Database(db_config)
                datasets = db.get_datasets()
                print(f"Success! Found {len(datasets)} datasets.")
                db.close()
            except Exception as e:
                print(f"Database connection failed: {e}")

            # 2. Verify Solr
            print("\n[2] Verifying Solr Connection...")
            solr_url = f"http://localhost:{ports['solr']}/solr"
            # We need a core name. Let's assume 'small' or get from env
            core = os.getenv("SOLR_CORE", "small")
            solr = SolrRetriever(solr_url, core)
            results = solr.search("test", limit=1)
            print(f"Solr search executed. Found {len(results)} results.")

            # 3. Verify Qdrant
            print("\n[3] Verifying Qdrant Connection...")
            qdrant_host = "localhost"
            qdrant_port = ports['qdrant']
            collection = os.getenv("QDRANT_COLLECTION", "documents")
            qdrant = QdrantRetriever(qdrant_host, qdrant_port, collection)
            # We need a vector dimension. Assuming 768 for now.
            results = qdrant.search(get_mock_vector(), limit=1)
            print(f"Qdrant search executed. Found {len(results)} results.")

            # 4. Verify Hybrid
            print("\n[4] Verifying Hybrid Retrieval...")
            hybrid = HybridRetriever(solr, qdrant)
            results = hybrid.search("test", get_mock_vector(), limit=5)
            print(f"Hybrid search executed. Top result score: {results[0].score if results else 'N/A'}")
            
            print("\nVerification Complete!")

    except Exception as e:
        print(f"\nVerification Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

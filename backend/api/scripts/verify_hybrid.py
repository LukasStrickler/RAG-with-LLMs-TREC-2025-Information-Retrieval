import logging
import os
import sys
from pathlib import Path

# Add backend/api to path so we can import app
sys.path.append(str(Path(__file__).parent.parent))

from app.services.retrieve.service import RetrievalService  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    print("Starting Hybrid Retrieval Verification (API Integration)...")

    # Check env vars
    required_vars = ["SSH_HOST", "SSH_USER"]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}")
        print(
            "Please set SSH_HOST, SSH_USER (and SSH_KEY_PATH or SSH_PASSWORD) before running."
        )
        sys.exit(1)

    service = RetrievalService()
    try:
        service.startup()

        # Test Query
        query_text = "twin tower adress"
        print(f"\nPerforming search for: '{query_text}'")

        # Hybrid
        print("\n[Hybrid Search]")
        result = service.generate_response(
            query_id="test_1", query_text=query_text, top_k=20, mode="hybrid"
        )
        print(f"Found {len(result.segments)} segments.")
        for seg in result.segments:
            print(f" - {seg.segment_id} (score: {seg.score:.4f})")

        # Lexical
        print("\n[Lexical Search]")
        result = service.generate_response(
            query_id="test_2", query_text=query_text, top_k=20, mode="lexical"
        )
        print(f"Found {len(result.segments)} segments.")

        # Vector
        print("\n[Vector Search]")
        result = service.generate_response(
            query_id="test_3", query_text=query_text, top_k=5, mode="vector"
        )
        print(f"Found {len(result.segments)} segments.")

    except Exception as e:
        logger.error(f"Verification failed: {e}")
        import traceback

        traceback.print_exc()
    finally:
        service.shutdown()
        print("\nVerification Complete!")


if __name__ == "__main__":
    main()

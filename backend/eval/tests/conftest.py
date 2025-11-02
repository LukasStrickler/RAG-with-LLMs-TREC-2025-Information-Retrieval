"""
pytest configuration and fixtures.
"""

import logging
from pathlib import Path

import pytest

from eval_cli.config import Config
from eval_cli.io.qrels import Qrels
from eval_cli.io.topics import TopicSet

logger = logging.getLogger(__name__)


@pytest.fixture
def config() -> Config:
    """Load test configuration."""
    try:
        return Config.load()
    except FileNotFoundError as e:
        pytest.fail(f"Configuration file not found: {e}")
    except Exception as e:
        pytest.fail(f"Error loading configuration: {e}")


@pytest.fixture
def test_data_dir() -> Path:
    """Get test data directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_topics_trec(test_data_dir: Path) -> TopicSet:
    """Load sample TREC topics."""
    from eval_cli.io.topics import load_topics

    topic_file = test_data_dir / "topics_sample.txt"
    if not topic_file.exists():
        pytest.fail(f"Test fixture file not found: {topic_file}")

    try:
        return load_topics(topic_file)
    except Exception as e:
        pytest.fail(f"Error loading topics fixture: {e}")


@pytest.fixture
def sample_topics_jsonl(test_data_dir: Path) -> TopicSet:
    """Load sample JSONL topics."""
    from eval_cli.io.topics import load_topics

    topic_file = test_data_dir / "topics_sample.jsonl"
    if not topic_file.exists():
        pytest.fail(f"Test fixture file not found: {topic_file}")

    try:
        return load_topics(topic_file)
    except Exception as e:
        pytest.fail(f"Error loading topics fixture: {e}")


@pytest.fixture
def sample_qrels(test_data_dir: Path) -> Qrels:
    """Load sample qrels.

    Returns:
        Qrels object containing relevance judgements.
        Note: The second tuple element (stats dict) is discarded.
    """
    from eval_cli.io.qrels import load_qrels

    qrels_file = test_data_dir / "qrels_sample.txt"
    if not qrels_file.exists():
        pytest.fail(f"Test fixture file not found: {qrels_file}")

    try:
        qrels, _metadata = load_qrels(
            qrels_file
        )  # metadata stats dict intentionally unused
        return qrels
    except Exception as e:
        pytest.fail(f"Error loading qrels fixture: {e}")

"""
pytest configuration and fixtures.
"""

from pathlib import Path

import pytest

from eval_cli.config import Config


@pytest.fixture
def config():
    """Load test configuration."""
    return Config.load()


@pytest.fixture
def test_data_dir():
    """Get test data directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_topics_trec(test_data_dir):
    """Load sample TREC topics."""
    from eval_cli.io.topics import load_topics

    return load_topics(test_data_dir / "topics_sample.txt")


@pytest.fixture
def sample_topics_jsonl(test_data_dir):
    """Load sample JSONL topics."""
    from eval_cli.io.topics import load_topics

    return load_topics(test_data_dir / "topics_sample.jsonl")


@pytest.fixture
def sample_qrels(test_data_dir):
    """Load sample qrels."""
    from eval_cli.io.qrels import load_qrels

    return load_qrels(test_data_dir / "qrels_sample.txt")

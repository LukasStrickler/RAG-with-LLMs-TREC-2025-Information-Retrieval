"""
Basic tests for the evaluation CLI.
"""

import pytest
from pathlib import Path
from eval_cli.config import Config
from eval_cli.io.topics import load_topics
from eval_cli.io.qrels import load_qrels
from eval_cli.models.topics import Topic, TopicSet


def test_config_loading():
    """Test configuration loading."""
    config = Config.load()
    assert config.api.base_url == "http://localhost:8000"
    assert config.retrieval.top_k == 100
    assert "rag24" in config.paths.topics
    assert "rag25" in config.paths.topics


def test_topic_loading():
    """Test topic loading from fixtures."""
    # Test TREC format
    trec_path = Path(__file__).parent / "fixtures" / "topics_sample.txt"
    topic_set = load_topics(trec_path)
    assert len(topic_set) > 0
    assert topic_set.format == "trec"
    
    # Test JSONL format
    jsonl_path = Path(__file__).parent / "fixtures" / "topics_sample.jsonl"
    topic_set = load_topics(jsonl_path)
    assert len(topic_set) > 0
    assert topic_set.format == "jsonl"


def test_qrels_loading():
    """Test qrels loading from fixtures."""
    qrels_path = Path(__file__).parent / "fixtures" / "qrels_sample.txt"
    qrels = load_qrels(qrels_path)
    assert len(qrels.entries) > 0
    assert len(qrels.get_query_ids()) > 0


def test_topic_model():
    """Test topic model functionality."""
    topic = Topic(
        query_id="1",
        query="test query",
        narrative="test narrative"
    )
    assert topic.query_length == 2
    assert topic.query_id == "1"


def test_topic_set():
    """Test topic set functionality."""
    topics = [
        Topic(query_id="1", query="query 1"),
        Topic(query_id="2", query="query 2"),
    ]
    topic_set = TopicSet(
        topics=topics,
        source_file="test.txt",
        format="trec"
    )
    assert len(topic_set) == 2
    assert topic_set.get_by_id("1") is not None
    assert topic_set.get_by_id("3") is None
    assert topic_set.query_ids == ["1", "2"]

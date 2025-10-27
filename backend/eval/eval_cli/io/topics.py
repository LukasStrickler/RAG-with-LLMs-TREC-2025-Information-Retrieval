"""
Topic loading and parsing utilities.
"""

import json
from pathlib import Path

from eval_cli.models.topics import Topic, TopicSet


def load_jsonl_topics(file_path: Path) -> TopicSet:
    """Load topics from JSONL format (2025 style)."""
    topics = []
    with open(file_path) as f:
        for line in f:
            data = json.loads(line)
            topic = Topic(
                query_id=data["query_id"],
                query=data["query"],
                narrative=data.get("narrative"),
                question=data.get("question"),
            )
            topics.append(topic)

    return TopicSet(topics=topics, source_file=str(file_path), format="jsonl")


def load_simple_topics(file_path: Path) -> TopicSet:
    """Load topics from simple tab-separated format (query_id\tquery_text)."""
    topics = []

    with open(file_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.split("\t", 1)
            if len(parts) == 2:
                query_id, query_text = parts
                topic = Topic(
                    query_id=query_id.strip(), query=query_text.strip(), narrative=""
                )
                topics.append(topic)

    return TopicSet(topics=topics, source_file=str(file_path), format="simple")


def load_trec_topics(file_path: Path) -> TopicSet:
    """Load topics from legacy TREC format (2024 style)."""
    topics = []
    current_topic = {}
    current_field = None

    with open(file_path) as f:
        for line in f:
            line = line.strip()

            if line.startswith("<top>"):
                current_topic = {}
            elif line.startswith("</top>"):
                if current_topic:
                    topic = Topic(
                        query_id=current_topic.get("num", ""),
                        query=current_topic.get("query", ""),
                        narrative=current_topic.get("narr"),
                    )
                    topics.append(topic)
            elif line.startswith("<num>"):
                current_topic["num"] = (
                    line.replace("<num>", "").replace("</num>", "").strip()
                )
            elif line.startswith("<query>"):
                current_topic["query"] = (
                    line.replace("<query>", "").replace("</query>", "").strip()
                )
            elif line.startswith("<narr>"):
                current_field = "narr"
                current_topic["narr"] = ""
            elif line.startswith("</narr>"):
                current_field = None
            elif current_field == "narr":
                current_topic["narr"] += " " + line

    return TopicSet(topics=topics, source_file=str(file_path), format="trec")


def load_topics(file_path: Path) -> TopicSet:
    """Auto-detect format and load topics."""
    if file_path.suffix == ".jsonl":
        return load_jsonl_topics(file_path)
    else:
        # Check if it's simple tab-separated format
        with open(file_path) as f:
            first_line = f.readline().strip()
            if "\t" in first_line and not first_line.startswith("<"):
                return load_simple_topics(file_path)
        return load_trec_topics(file_path)

"""
Topic loading and parsing utilities.
"""

import json
import logging
from pathlib import Path

from eval_cli.models.topics import Topic, TopicSet

logger = logging.getLogger(__name__)


def load_jsonl_topics(file_path: Path) -> TopicSet:
    """Load topics from JSONL format (2025 style)."""
    topics = []
    try:
        with open(file_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    data = json.loads(line)
                    topic = Topic(
                        query_id=data["query_id"],
                        query=data["query"],
                        narrative=data.get("narrative"),
                        question=data.get("question"),
                    )
                    topics.append(topic)
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Invalid JSON on line {line_num} in {file_path}: {e}. "
                        f"Line: {line[:100]}"
                    )
                    continue
                except KeyError as e:
                    logger.warning(
                        f"Missing required field on line {line_num} in {file_path}: {e}. "
                        f"Line: {line[:100]}"
                    )
                    continue
    except FileNotFoundError:
        raise
    except OSError as e:
        raise RuntimeError(f"Error reading topics file {file_path}: {e}") from e

    return TopicSet(topics=topics, source_file=str(file_path), format="jsonl")


def load_simple_topics(file_path: Path) -> TopicSet:
    """Load topics from simple tab-separated format (query_id\tquery_text)."""
    topics = []

    try:
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                parts = line.split("\t", 1)
                if len(parts) == 2:
                    query_id, query_text = parts
                    topic = Topic(
                        query_id=query_id.strip(),
                        query=query_text.strip(),
                        narrative="",
                    )
                    topics.append(topic)
                else:
                    logger.warning(
                        f"Malformed line in simple topics file {file_path} "
                        f"(expected tab-separated query_id and query): {line[:100]}"
                    )
    except FileNotFoundError:
        raise
    except OSError as e:
        raise RuntimeError(f"Error reading topics file {file_path}: {e}") from e

    return TopicSet(topics=topics, source_file=str(file_path), format="simple")


def load_trec_topics(file_path: Path) -> TopicSet:
    """Load topics from legacy TREC format (2024 style)."""
    topics = []
    current_topic = {}
    current_field = None

    try:
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if line.startswith("<top>"):
                    current_topic = {}
                elif line.startswith("</top>"):
                    if current_topic:
                        query_id = current_topic.get("num", "").strip()
                        query = current_topic.get("query", "").strip()

                        # Validate required fields before creating Topic
                        if not query_id:
                            logger.warning(
                                f"Topic block missing required field 'num' (query_id) in {file_path}. "
                                f"Skipping incomplete topic."
                            )
                        elif not query:
                            logger.warning(
                                f"Topic block with query_id '{query_id}' missing required field 'query' in {file_path}. "
                                f"Skipping incomplete topic."
                            )
                        else:
                            topic = Topic(
                                query_id=query_id,
                                query=query,
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
    except FileNotFoundError:
        raise
    except OSError as e:
        raise RuntimeError(f"Error reading topics file {file_path}: {e}") from e

    return TopicSet(topics=topics, source_file=str(file_path), format="trec")


def load_topics(file_path: Path) -> TopicSet:
    """Auto-detect format and load topics."""
    if not file_path.exists():
        raise FileNotFoundError(f"Topic file not found: {file_path}")

    if file_path.suffix == ".jsonl":
        return load_jsonl_topics(file_path)
    else:
        # Check if it's simple tab-separated format
        try:
            with open(file_path, encoding="utf-8") as f:
                first_line = f.readline().strip()
                if "\t" in first_line and not first_line.startswith("<"):
                    return load_simple_topics(file_path)
        except FileNotFoundError:
            raise
        except OSError as e:
            raise RuntimeError(f"Error reading topics file {file_path}: {e}") from e
        return load_trec_topics(file_path)

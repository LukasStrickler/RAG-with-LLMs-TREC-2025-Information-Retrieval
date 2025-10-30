"""
Qrels loading and parsing utilities.
"""

from pathlib import Path

from pydantic import BaseModel


class QrelEntry(BaseModel):
    """Single qrel entry."""

    query_id: str
    doc_id: str
    relevance: int


class Qrels(BaseModel):
    """Collection of relevance judgements."""

    entries: list[QrelEntry]

    def get_relevant_docs(self, query_id: str) -> set[str]:
        """Get all relevant documents for a query."""
        return {
            entry.doc_id
            for entry in self.entries
            if entry.query_id == query_id and entry.relevance > 0
        }

    def get_relevance_grades(self, query_id: str) -> dict[str, int]:
        """Get relevance grades for all documents in a query."""
        return {
            entry.doc_id: entry.relevance
            for entry in self.entries
            if entry.query_id == query_id
        }

    def get_query_ids(self) -> set[str]:
        """Get all query IDs."""
        return {entry.query_id for entry in self.entries}


def load_qrels(file_path: Path) -> tuple[Qrels, dict[str, int]]:
    """
    Load TREC qrels file.
    
    Args:
        file_path: Path to the qrels file
        
    Returns:
        Tuple of (Qrels, stats_dict).
        Stats dict contains:
        - 'malformed': count of lines with fewer than 3 fields
        - 'invalid_relevance': count of lines with non-integer relevance values
    """
    entries = []
    stats = {"malformed": 0, "invalid_relevance": 0}

    try:
        with open(file_path, encoding="utf-8") as f:
            for _line_num, line in enumerate(f, 1):
                parts = line.strip().split()
                if len(parts) < 3:
                    # Track malformed lines
                    stats["malformed"] += 1
                    continue
                try:
                    relevance = int(parts[3]) if len(parts) > 3 else 1
                    entry = QrelEntry(
                        query_id=parts[0],
                        doc_id=parts[2],
                        relevance=relevance,
                    )
                    entries.append(entry)
                except ValueError:
                    # Track lines with non-integer relevance
                    stats["invalid_relevance"] += 1
                    continue
    except FileNotFoundError:
        raise FileNotFoundError(f"Qrels file not found: {file_path}")
    except OSError as e:
        raise RuntimeError(f"Error reading qrels file {file_path}: {e}")

    qrels = Qrels(entries=entries)
    return qrels, stats

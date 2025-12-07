"""Database operations for the indexing pipeline."""

from datetime import datetime

import psycopg2


class Database:
    """PostgreSQL database operations."""

    def __init__(self, config: dict):
        self.conn = psycopg2.connect(**config)
        self.conn.set_session(readonly=True, autocommit=True)

    def get_datasets(self) -> list[dict]:
        """Fetch all datasets with document counts."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    d.id, d.name, d.version, d.split, d.release_date, d.source_uri,
                    COUNT(did.document_id) as doc_count
                FROM dataset d
                LEFT JOIN document_in_dataset did ON d.id = did.dataset_id
                GROUP BY d.id, d.name, d.version, d.split, d.release_date, d.source_uri
                ORDER BY d.name
            """
            )
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row, strict=False)) for row in cur.fetchall()]

    def get_dataset_by_name(self, name: str) -> dict | None:
        """Get dataset by name."""
        return next(
            (ds for ds in self.get_datasets() if ds["name"].lower() == name.lower()),
            None,
        )

    def get_document_ids(self, dataset_id: str, limit: int | None = None) -> list[str]:
        """Fetch document IDs for a dataset."""
        with self.conn.cursor() as cur:
            query = "SELECT document_id FROM document_in_dataset WHERE dataset_id = %s ORDER BY document_id"
            if limit:
                query += f" LIMIT {limit}"
            cur.execute(query, (dataset_id,))
            return [row[0] for row in cur.fetchall()]

    def get_documents(self, doc_ids: list[str]) -> list[dict]:
        """Fetch full documents by IDs."""
        documents = []
        batch_size = 1000

        for i in range(0, len(doc_ids), batch_size):
            batch = doc_ids[i : i + batch_size]
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, url, title, body, length, created_at, updated_at
                    FROM documents WHERE id = ANY(%s)
                """,
                    (batch,),
                )

                columns = [desc[0] for desc in cur.description]
                for row in cur.fetchall():
                    doc = dict(zip(columns, row, strict=False))
                    # Convert datetime to ISO string
                    for k, v in doc.items():
                        if isinstance(v, datetime):
                            doc[k] = v.isoformat()
                    documents.append(doc)

        return documents

    def close(self):
        """Close connection."""
        self.conn.close()

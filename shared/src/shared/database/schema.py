from uuid import UUID
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

# --- 1. DATASET MODEL ---
class Dataset(BaseModel):
    id: Optional[UUID] = None
    name: str
    version: Optional[str] = None
    split: Optional[str] = None
    release_date: Optional[str] = None
    source_uri: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- 2. CHUNKING SPEC MODEL ---
class ChunkingSpec(BaseModel):
    id: Optional[UUID] = None
    dataset_id: Optional[UUID] = None
    chunk_size: Optional[int] = None
    overlap: Optional[int] = None
    tokenizer: Optional[str] = None
    strategy: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- 3. INDEX TARGET MODEL ---
class IndexTarget(BaseModel):
    id: Optional[UUID] = None
    dataset_id: Optional[UUID] = None
    kind: Optional[str] = None
    uri: Optional[str] = None
    snapshot_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- 4. SEGMENT MODEL ---
class Segment(BaseModel):
    id: str  # Im Diagramm als TEXT definiert
    dataset_id: UUID
    content: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    # 'Any' erlaubt flexible JSON-Strukturen, Dict[str, Any] ist strenger
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)
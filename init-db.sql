-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create dataset table
CREATE TABLE IF NOT EXISTS dataset
(
    id           UUID DEFAULT uuid_generate_v4() NOT NULL PRIMARY KEY,
    name         TEXT                            NOT NULL,
    version      TEXT,
    split        TEXT,
    release_date TEXT,
    source_uri   TEXT
);

ALTER TABLE dataset OWNER TO postgres;

-- Create chunking_spec table
CREATE TABLE IF NOT EXISTS chunking_spec
(
    id         UUID DEFAULT uuid_generate_v4() NOT NULL PRIMARY KEY,
    dataset_id UUID                            NOT NULL
        CONSTRAINT fk_chunking_dataset
            REFERENCES dataset
            ON DELETE CASCADE,
    chunk_size INTEGER,
    overlap    INTEGER,
    tokenizer  TEXT,
    strategy   TEXT
);

ALTER TABLE chunking_spec OWNER TO postgres;

-- Create index_target table
CREATE TABLE IF NOT EXISTS index_target
(
    id          UUID DEFAULT uuid_generate_v4() NOT NULL PRIMARY KEY,
    dataset_id  UUID                            NOT NULL
        CONSTRAINT fk_index_dataset
            REFERENCES dataset
            ON DELETE CASCADE,
    kind        TEXT,
    uri         TEXT,
    snapshot_id TEXT
);

ALTER TABLE index_target OWNER TO postgres;

-- Create segment table
CREATE TABLE IF NOT EXISTS segment
(
    id         TEXT NOT NULL PRIMARY KEY,
    dataset_id UUID NOT NULL
        CONSTRAINT fk_segment_dataset
            REFERENCES dataset
            ON DELETE CASCADE,
    content    TEXT,
    title      TEXT,
    url        TEXT,
    metadata   JSONB
);

ALTER TABLE segment OWNER TO postgres;

-- Create documents table
CREATE TABLE IF NOT EXISTS documents
(
    id         TEXT                                   NOT NULL PRIMARY KEY,
    url        TEXT,
    title      TEXT,
    body       TEXT,
    length     INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

ALTER TABLE documents OWNER TO postgres;

-- Create indexes on documents table
CREATE INDEX IF NOT EXISTS documents_url_idx ON documents (url);
CREATE INDEX IF NOT EXISTS documents_length_idx ON documents (length);

-- Create trigger for documents updated_at
DROP TRIGGER IF EXISTS trg_documents_set_updated_at ON documents;
CREATE TRIGGER trg_documents_set_updated_at
    BEFORE UPDATE
    ON documents
    FOR EACH ROW
EXECUTE PROCEDURE set_updated_at();

-- Create document_in_dataset table
CREATE TABLE IF NOT EXISTS document_in_dataset
(
    dataset_id  UUID                                   NOT NULL
        CONSTRAINT fk_did_dataset
            REFERENCES dataset
            ON DELETE CASCADE,
    document_id TEXT                                   NOT NULL
        CONSTRAINT fk_did_document
            REFERENCES documents
            ON DELETE CASCADE,
    added_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    PRIMARY KEY (dataset_id, document_id)
);

ALTER TABLE document_in_dataset OWNER TO postgres;

-- Create index on document_in_dataset
CREATE INDEX IF NOT EXISTS did_document_idx ON document_in_dataset (document_id);

-- Create documents_stg table
CREATE TABLE IF NOT EXISTS documents_stg
(
    payload JSONB
);

ALTER TABLE documents_stg OWNER TO postgres;

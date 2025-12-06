import orjson
import psycopg2
import os
import io
import csv
import zipfile
import glob
from pathlib import Path
from typing import Iterator

# --- KONFIGURATION ---
# Local Docker PostgreSQL (from docker-compose.yml)
USE_LOCAL = True  # Set to False to use SSH tunnel to remote server
DB_HOST = "localhost"
DB_PORT = 5433  # Docker exposes PostgreSQL on port 5433
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "password"

# SSH Configuration (only used if USE_LOCAL = False)
SSH_HOST = ''
SSH_USER = "root"
SSH_PASSWORD = ''
DB_REMOTE_BIND_ADDRESS = ''
DB_REMOTE_PORT = 5432

# Dataset Configuration
DATASET_DIR = "../dataset"  # Directory containing .jsonl or .jsonl.zip files
PROGRESS_FILE = "import_progress.txt"
DATASET_ID = "997df93a-0b19-4734-922a-1728509fada7"

# Batch size for COPY operations
BATCH_SIZE = 50000


def load_progress():
    """Reads the last saved progress (file_index, line_number)."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r') as f:
                content = f.read().strip()
                if ',' in content:
                    file_idx, line_num = content.split(',')
                    return int(file_idx), int(line_num)
                elif content:
                    return 0, int(content)
        except (ValueError, IndexError):
            pass
    return 0, 0


def save_progress(file_index, line_number):
    """Saves the current progress."""
    with open(PROGRESS_FILE, 'w') as f:
        f.write(f"{file_index},{line_number}")


def clean_text(value):
    """Removes NUL bytes and cleans strings."""
    if isinstance(value, str):
        return value.replace('\x00', '')
    return value


def get_dataset_files():
    """Gets all dataset files (both .jsonl and .jsonl.zip), sorted."""
    dataset_path = Path(DATASET_DIR)
    files = []
    
    # Find .jsonl files
    files.extend(glob.glob(str(dataset_path / "*.jsonl")))
    # Find .jsonl.zip files
    files.extend(glob.glob(str(dataset_path / "*.jsonl.zip")))
    
    # Sort files (handles both part_0000 and single files)
    files.sort()
    return files


def open_dataset_file(filepath):
    """Opens a dataset file, handling both regular and zipped files."""
    # Check if file is a Git LFS pointer
    with open(filepath, 'rb') as f:
        first_line = f.readline()
        if first_line.startswith(b'version https://git-lfs.github.com'):
            raise ValueError(
                f"File {Path(filepath).name} is a Git LFS pointer, not the actual data.\n"
                f"Please run: git lfs pull\n"
                f"Or if Git LFS is not installed: brew install git-lfs && git lfs install && git lfs pull"
            )
    
    if filepath.endswith('.zip'):
        # Try to open as zip file
        try:
            zf = zipfile.ZipFile(filepath, 'r')
            jsonl_files = [name for name in zf.namelist() if name.endswith('.jsonl')]
            if not jsonl_files:
                raise ValueError(f"No .jsonl file found in {filepath}")
            # Return a file-like object
            return io.TextIOWrapper(zf.open(jsonl_files[0], 'r'), encoding='utf-8'), zf
        except zipfile.BadZipFile:
            # If it's not actually a zip file, treat it as plain text JSONL
            # (Some files may have .zip extension but be plain text)
            print(f"  Note: {Path(filepath).name} has .zip extension but is not compressed, reading as plain text")
            return open(filepath, 'r', encoding='utf-8'), None
    else:
        # Open regular file
        return open(filepath, 'r', encoding='utf-8'), None


def get_connection():
    """Establishes database connection (local or via SSH tunnel)."""
    if USE_LOCAL:
        print(f"Connecting to local PostgreSQL at {DB_HOST}:{DB_PORT}...")
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            dbname=DB_NAME
        )
        return conn, None
    else:
        from sshtunnel import SSHTunnelForwarder
        print(f"Building SSH tunnel to {SSH_HOST}...")
        tunnel = SSHTunnelForwarder(
            (SSH_HOST, 22),
            ssh_username=SSH_USER,
            ssh_password=SSH_PASSWORD,
            remote_bind_address=(DB_REMOTE_BIND_ADDRESS, DB_REMOTE_PORT),
            host_pkey_directories=[]
        )
        tunnel.start()
        print(f"Connected! Local port: {tunnel.local_bind_port}")
        
        conn = psycopg2.connect(
            host='127.0.0.1',
            port=tunnel.local_bind_port,
            user=DB_USER,
            password=DB_PASS,
            dbname=DB_NAME
        )
        return conn, tunnel


def process_files():
    """Processes all dataset files with resume capability."""
    files = get_dataset_files()
    
    if not files:
        print(f"Error: No dataset files found in {DATASET_DIR}")
        print("Looking for *.jsonl or *.jsonl.zip files")
        return

    start_file_idx, start_line = load_progress()
    
    if start_file_idx > 0 or start_line > 0:
        print(f"Resuming from file {start_file_idx}, line {start_line:,}...")
    else:
        print("Starting new import...")

    print(f"Found {len(files)} file(s) to process:")
    for i, f in enumerate(files):
        status = "✓ Done" if i < start_file_idx else ("→ Current" if i == start_file_idx else "  Pending")
        print(f"  [{status}] {Path(f).name}")

    try:
        conn, tunnel = get_connection()
        cursor = conn.cursor()

        # Ensure dataset exists
        cursor.execute("""
            INSERT INTO public.dataset (id, name, version, split, release_date, source_uri)
            VALUES (%s, 'MS MARCO', 'v1', 'sample', '2024-01-01', 'https://microsoft.github.io/msmarco/')
            ON CONFLICT (id) DO NOTHING;
        """, (DATASET_ID,))
        conn.commit()
        print(f"Dataset record ensured (ID: {DATASET_ID})")

        # Performance tuning
        cursor.execute("SET synchronous_commit = OFF;")

        # Create temp table for COPY
        cursor.execute("""
            CREATE TEMP TABLE IF NOT EXISTS tmp_load (
                id text,
                url text,
                title text,
                body text,
                length int
            );
        """)

        print("\nStarting high-speed import...")
        cursor.execute("TRUNCATE tmp_load;")

        total_imported = 0
        
        # Process each file
        for file_idx, filepath in enumerate(files):
            # Skip already processed files
            if file_idx < start_file_idx:
                continue

            print(f"\n{'='*60}")
            print(f"Processing file {file_idx + 1}/{len(files)}: {Path(filepath).name}")
            print(f"{'='*60}")

            csv_buffer = io.StringIO()
            csv_writer = csv.writer(csv_buffer, delimiter='\t', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            rows_in_batch = 0
            file_imported = 0

            # Open file (handles both zipped and unzipped)
            file_handle, zip_handle = open_dataset_file(filepath)
            
            try:
                for line_idx, line in enumerate(file_handle):
                    # Skip lines if resuming
                    if file_idx == start_file_idx and line_idx < start_line:
                        continue

                    # Parse JSON
                    try:
                        data = orjson.loads(line)
                    except (orjson.JSONDecodeError, ValueError):
                        continue

                    # Extract data
                    doc_id_raw = data.get('id') or data.get('docid')
                    if not doc_id_raw:
                        continue
                    doc_id = clean_text(str(doc_id_raw))

                    body = clean_text(data.get('text') or data.get('body') or "")
                    length = data.get('length') or len(body)

                    # Write to CSV buffer
                    csv_writer.writerow([
                        doc_id,
                        clean_text(data.get('url')),
                        clean_text(data.get('title')),
                        body,
                        int(length)
                    ])

                    rows_in_batch += 1

                    # Batch full? Write to DB
                    if rows_in_batch >= BATCH_SIZE:
                        csv_buffer.seek(0)

                        # 1. COPY to temp table (high speed)
                        cursor.copy_expert(
                            "COPY tmp_load (id, url, title, body, length) FROM STDIN WITH (FORMAT CSV, DELIMITER '\t')",
                            csv_buffer
                        )

                        # 2. UPSERT into documents table
                        cursor.execute("""
                            INSERT INTO public.documents (id, url, title, body, length)
                            SELECT id, url, title, body, length
                            FROM tmp_load 
                            ON CONFLICT (id) DO UPDATE
                                SET url = EXCLUDED.url,
                                    title = EXCLUDED.title,
                                    body = EXCLUDED.body,
                                    length = EXCLUDED.length;
                        """)

                        # 3. Link to dataset
                        cursor.execute("""
                            INSERT INTO public.document_in_dataset (dataset_id, document_id)
                            SELECT %s, id
                            FROM tmp_load 
                            ON CONFLICT DO NOTHING;
                        """, (DATASET_ID,))

                        # Clean up and commit
                        cursor.execute("TRUNCATE tmp_load;")
                        conn.commit()

                        save_progress(file_idx, line_idx + 1)
                        file_imported += rows_in_batch
                        total_imported += rows_in_batch
                        print(f"  → Line {line_idx + 1:,} | Batch: {rows_in_batch:,} docs | Total: {total_imported:,}")

                        # Reset buffer
                        csv_buffer.close()
                        csv_buffer = io.StringIO()
                        csv_writer = csv.writer(csv_buffer, delimiter='\t', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                        rows_in_batch = 0

                # Import remaining rows from buffer
                if rows_in_batch > 0:
                    csv_buffer.seek(0)
                    cursor.copy_expert(
                        "COPY tmp_load (id, url, title, body, length) FROM STDIN WITH (FORMAT CSV, DELIMITER '\t')",
                        csv_buffer
                    )

                    cursor.execute("""
                        INSERT INTO public.documents (id, url, title, body, length)
                        SELECT id, url, title, body, length
                        FROM tmp_load 
                        ON CONFLICT (id) DO UPDATE
                            SET url = EXCLUDED.url,
                                title = EXCLUDED.title,
                                body = EXCLUDED.body,
                                length = EXCLUDED.length;
                    """)

                    cursor.execute("""
                        INSERT INTO public.document_in_dataset (dataset_id, document_id)
                        SELECT %s, id
                        FROM tmp_load 
                        ON CONFLICT DO NOTHING;
                    """, (DATASET_ID,))

                    conn.commit()
                    file_imported += rows_in_batch
                    total_imported += rows_in_batch
                    print(f"  → Remaining {rows_in_batch:,} documents imported.")

                print(f"✓ File complete: {file_imported:,} documents imported")
                
                # Mark file as complete
                save_progress(file_idx + 1, 0)
                
            finally:
                file_handle.close()
                if zip_handle:
                    zip_handle.close()

        print(f"\n{'='*60}")
        print(f"✓ COMPLETE! All {total_imported:,} documents successfully imported.")
        print(f"{'='*60}")
        
        cursor.close()
        conn.close()
        
        if tunnel:
            tunnel.stop()

        # Clean up progress file on successful completion
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)

    except Exception as e:
        print(f"\n{'='*60}")
        print(f"✗ CRITICAL ERROR: {e}")
        print(f"{'='*60}")
        print("Tip: Restart the script - it will resume from the last checkpoint.")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    process_files()
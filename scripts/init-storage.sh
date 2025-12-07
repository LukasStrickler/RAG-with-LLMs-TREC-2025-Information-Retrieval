#!/usr/bin/env bash

# init-storage.sh - Automatically reconstruct and extract backup files for Docker storage
# This script combines split backup files and extracts them to the appropriate directories

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
IMAGES_DIR="$PROJECT_ROOT/images"

echo "🔧 Initializing storage from backup files..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Change to images directory
cd "$IMAGES_DIR"

# Function to combine and extract backup
combine_and_extract() {
    local base_name="$1"
    local target_dir="$2"
    local tar_file="${base_name}.tar.gz"
    
    echo ""
    echo "📦 Processing $base_name..."
    
    # Check if split files exist
    if ! ls "${base_name}.tar.gz.part-"* 1> /dev/null 2>&1; then
        echo "⚠️  Warning: No split files found for $base_name"
        
        # Check if tar.gz already exists
        if [ -f "$tar_file" ]; then
            echo "✓ Found existing $tar_file"
        else
            echo "❌ Error: Neither split files nor tar.gz found for $base_name"
            return 1
        fi
    else
        # Combine split files if tar.gz doesn't exist or is older than split files
        if [ ! -f "$tar_file" ] || [ "$(ls -t "${base_name}.tar.gz.part-"* | head -1)" -nt "$tar_file" ]; then
            echo "  → Combining split files..."
            cat "${base_name}.tar.gz.part-"* > "$tar_file"
            echo "  ✓ Combined into $tar_file"
        else
            echo "  ✓ Using existing $tar_file (up to date)"
        fi
    fi
    
    # Create target directory if it doesn't exist
    mkdir -p "$target_dir"
    
    # Check if already extracted (has files)
    if [ "$(ls -A "$target_dir" 2>/dev/null)" ]; then
        echo "  ✓ Directory $target_dir already populated"
        echo "  → Skipping extraction (use --force to re-extract)"
    else
        echo "  → Extracting to $target_dir..."
        tar -xzf "$tar_file" -C "$target_dir"
        echo "  ✓ Extracted successfully"
    fi
}

# Parse arguments
FORCE_EXTRACT=0
if [ "$1" = "--force" ]; then
    FORCE_EXTRACT=1
    echo "⚠️  Force mode: Will re-extract even if directories exist"
fi

# Process Solr backup
if [ $FORCE_EXTRACT -eq 1 ] && [ -d "solr_data_backup" ]; then
    echo "  → Removing existing solr_data_backup..."
    rm -rf solr_data_backup
fi
combine_and_extract "solr_backup_optimized" "solr_data_backup"

# Process Qdrant backup
if [ $FORCE_EXTRACT -eq 1 ] && [ -d "qdrant_data_backup" ]; then
    echo "  → Removing existing qdrant_data_backup..."
    rm -rf qdrant_data_backup
fi
combine_and_extract "qdrant_backup" "qdrant_data_backup"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Storage initialization complete!"
echo ""
echo "Directory sizes:"
du -sh solr_data_backup 2>/dev/null || echo "  solr_data_backup: not found"
du -sh qdrant_data_backup 2>/dev/null || echo "  qdrant_data_backup: not found"
echo ""
echo "You can now run: docker-compose up -d"

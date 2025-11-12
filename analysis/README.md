# Qrels Essential Documents Analysis

This directory contains a Jupyter notebook for analyzing qrels data to identify mandatory documents required for evaluation and understand document distribution patterns.

## Setup

1. **Install Poetry dependencies:**
   ```bash
   cd analysis
   poetry install
   ```

2. **Register Jupyter kernel (one-time setup):**
   ```bash
   ./setup_kernel.sh
   ```
   
   This registers a kernel named "corpus-analysis" that uses the Poetry environment.

3. **Start Jupyter:**
   ```bash
   poetry run jupyter notebook
   ```

4. **Open the notebook:**
   - Open `qrels_essential_analysis.ipynb`
   - The notebook is pre-configured to use the "Python (corpus-analysis)" kernel
   - If prompted, select "Python (corpus-analysis)" from Kernel > Change Kernel
   - Run all cells to perform the analysis

## Key Understanding

- **If ANY segment of a document is in qrels → include the ENTIRE document (all segments)**
- **Mandatory:** All base documents that have at least one segment in qrels
- **Optional:** Documents with no segments in qrels (can be stratify sampled)

## Analysis Sections

The notebook includes 10 comprehensive sections:

1. **Setup and Load Qrels** - Load and parse qrels data
2. **Mandatory Base Documents** - Identify all required documents
3. **Document Completeness Analysis** - Analyze segment coverage per document
4. **Distribution Analysis** - Domain and segment distributions
5. **Relevance Frequency Analysis** - How often documents are relevant
6. **Query-Document Relationships** - Documents per query analysis
7. **Mandatory vs Optional** - Separate mandatory from optional documents
8. **KPI Calculation Requirements** - What's needed for evaluation
9. **Visualizations** - Comprehensive charts and plots
10. **Summary and Recommendations** - Final findings and recommendations

## Output

The notebook generates a CSV file in the `data/` directory:

- `mandatory_base_documents.csv` - All mandatory base document IDs with metadata

Each CSV contains:
- `base_doc_id` - Base document ID (mandatory for evaluation)
- `query_count` - Number of queries referencing this document
- `max_relevance` - Maximum relevance grade
- `avg_relevance` - Average relevance grade
- `qrels_segment_count` - Number of qrels segments in this document
- `domain` - 2-digit domain prefix

## Requirements

- Python 3.11+
- Poetry for dependency management
- Jupyter Notebook

See `pyproject.toml` for full dependency list.



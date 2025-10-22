# Retrieval KPI Reference — TREC 2025 (R Task)

> Quick reference for core ranking metrics used in our retrieval experiments.
> Includes definitions, interpretation, target ranges, and links to supporting material.

---

## Evaluation Fundamentals

**Why multiple metrics matter:**
- **Precision vs Recall** trade-offs—more docs = higher recall, lower precision
- **Ranking order** critical—users examine top results first
- **Graded relevance**—documents aren't just relevant/not relevant

**Test collection components:**
- **Documents** to search
- **Information needs** (queries)
- **Relevance judgements** (`qrels`)
- **Dev/test splits** prevent overfitting

---

## Summary Table

| Metric | Treated As | Typical Baseline (BM25) | Competitive Target | Notes |
| --- | --- | --- | --- | --- |
| nDCG@10 | ↑ higher is better | ~0.30–0.32 | ≥0.35 (good), ≥0.40 (strong) | Primary leaderboard metric; rewards early, high-graded hits. |
| MAP@100 | ↑ higher is better | ~0.25–0.27 | +0.03–0.05 uplift is meaningful | Balances precision/recall over 100 ranks. |
| MRR@10 | ↑ higher is better | ~0.45 | ≥0.55 | Diagnoses how quickly the first relevant result appears. |
| Recall@50 | ↑ higher is better | ~0.55–0.60 | ≥0.62 | Coverage within top 50. Ensure pools are deep enough. |
| Recall@100 | ↑ higher is better | ~0.60–0.65 | ≥0.70 | Aligns with TREC 100-doc submission cap. |
| HitRate@10 | ↑ higher is better | ~0.70–0.75 | ≥0.80 | Internal diagnostic: at least one relevant hit in top 10. |

All metrics are computed using `trec_eval` except HitRate@10, which we track in CLI post-processing.

---

## 1. Normalized Discounted Cumulative Gain @ 10 (nDCG@10)

**What it measures:**
- **Ranking quality** considering both relevance grades and position
- *Weights early, high-graded hits heavily*

**How it's calculated:**
- **CG**: Sum relevance scores (ignores position)
- **DCG**: Add logarithmic discount $\frac{1}{\log_2(i+1)}$ for position $i$
- **NDCG**: Normalize by $\mathrm{IDCG}$ (perfect ranking) for fair comparison

**Formula**
\[
\mathrm{nDCG@10} = \frac{1}{\mathrm{IDCG@10}} \sum_{i=1}^{10} \frac{2^{\mathrm{rel}_i}-1}{\log_2(i+1)}
\]

**Why it matters:**
- **Discount factor** models real user behavior—position $1 \gg$ position $10$
- **Normalization** prevents queries with many relevant docs from inflating scores
- **Primary leaderboard metric** for TREC competitions

---

## 2. Mean Average Precision @ 100 (MAP@100)

**What it measures:**
- **Ranking quality** of relevant documents in top 100
- *Heavily penalizes* systems that bury relevant docs lower in results

**How it's calculated:**
- **First average**: Calculate $\mathrm{AP}$ per query (average precision at each relevant doc)
- **Second average**: Mean $\mathrm{AP}$ scores across all queries
- **Double-averaging** ensures early relevant docs get higher scores

**Formula**
\[
\mathrm{MAP@100} = \frac{1}{|Q|} \sum_{q \in Q} \frac{1}{\min(|\mathrm{Rel}_q|, 100)} \sum_{k=1}^{100} P_q(k) \cdot \mathrm{rel}_q(k)
\]

**Why it matters:**
- **Ranking sensitive**—positions $1,2,4 \gg 2,5,6$ for same docs found
- **Balances precision/recall** across 100 ranks
- **Standard metric** for comparing retrieval systems

---

## 3. Mean Reciprocal Rank @ 10 (MRR@10)

**What it measures:**
- **First relevant hit** position in top 10 results
- *Ignores* all subsequent relevant documents

**How it's calculated:**
- Find **first relevant doc** rank $(1-10)$ per query
- Take **reciprocal** $\frac{1}{\mathrm{rank}}$ (or $0$ if none found)
- **Average** reciprocals across all queries

**Formula**
\[
\mathrm{MRR@10} = \frac{1}{|Q|} \sum_{q \in Q} \frac{1}{\mathrm{rank}_q}
\]
with \(\mathrm{rank}_q\) defined as the position of the first relevant segment if \(\le 10\), otherwise 0.

**Why it matters:**
- **QA systems**—users need just one good answer
- **Navigational queries**—finding specific page/site
- **Early-hit diagnostic**—complements MAP's comprehensive view

---

## 4. Recall @ 50 (Recall@50)

**What it measures:**
- **Fraction** of all relevant docs found in top 50
- **Comprehensiveness** indicator

**How it's calculated:**
- Count **relevant docs** in top 50 per query
- Divide by **total relevant docs** for that query
- **Average** fraction across all queries

**Formula**
\[
\mathrm{Recall@50} = \frac{1}{|Q|} \sum_{q \in Q} \frac{|\mathrm{Rel}_q \cap \mathrm{Retrieved}_{q,\le 50}|}{|\mathrm{Rel}_q|}
\]

**Why it matters:**
- **Pooling methodology**—connects to human annotation process
- **Computational efficiency**—50-doc cutoff balances depth vs speed
- **System comparison**—shows if we find docs other systems consider relevant

---

## 5. Recall @ 100 (Recall@100)

**What it measures:**
- **Fraction** of all relevant docs found in top 100
- **Maximum comprehensiveness** within practical limits

**How it's calculated:**
- Count **relevant docs** in top 100 per query
- Divide by **total relevant docs** for that query
- **Average** fraction across all queries

**Formula**
\[
\mathrm{Recall@100} = \frac{1}{|Q|} \sum_{q \in Q} \frac{|\mathrm{Rel}_q \cap \mathrm{Retrieved}_{q,\le 100}|}{|\mathrm{Rel}_q|}
\]

**Why it matters:**
- **TREC submission limit**—aligns with official 100-doc constraint
- **Competition evaluation**—critical for fair comparison
- **Real-world relevance**—matches practical system constraints

---

## 6. Hit Rate @ 10 (HitRate@10)

**What it measures:**
- **Binary success** rate—any relevant doc in top 10?
- **User satisfaction** proxy

**How it's calculated:**
- **Per query**: $1$ if any relevant doc in top $10$, else $0$
- **Average** binary outcomes across all queries
- **Simple percentage** of "successful" queries

**Formula**
\[
\mathrm{HitRate@10} = \frac{1}{|Q|} \sum_{q \in Q} \mathbf{1}\left[\mathrm{Rel}_q \cap \mathrm{Retrieved}_{q,\le 10} \neq \emptyset\right]
\]

**Why it matters:**
- **Fast diagnostic**—"Did user find anything useful?"
- **Query success rate**—correlates with user satisfaction
- **Ignores ranking quality**—just binary hit/miss

---

## Evaluation Workflow

1. Generate runs (`runs fetch`) and validate TREC formatting (`runs validate`).
   - **Validation**: Ensure runs files non-empty, all queries covered, TREC 6-column format, rank uniqueness per query, result depth ≤100
2. Score with `trec_eval -m ndcg_cut.10 -m map_cut.100 -m recip_rank -m recall.50 -m recall.100 qrels.txt run.tsv` (trec_eval 9.0.7).
3. Compute HitRate@10 in CLI post-processing (not in trec_eval).
   - **Post-processing**: Flag queries with zero judged relevants, ensure no negative/zero relevance grades
4. Log metrics in `EvaluationReport` and `ExperimentManifest` for reproducibility.
   - **Metadata**: Record model version, timestamp, parameters, index snapshots

**Recovery Actions**:
- Empty/invalid runs: Re-run generation, check query format
- Validation failures: Rebuild qrels, verify rank ordering
- Shallow pools: Mark runs as incomplete, document coverage

**Implementation:** Evaluation CLI (`backend/eval/`) handles run generation and validation.  
**Schema Reference:** Data contracts for `EvaluationReport` and `ExperimentManifest` are defined in [`.docs/uml/classes.puml`](./uml/classes.puml).

**Metric Name Mapping**: Display names (MRR@10) map to trec_eval names (recip_rank) for command-line compatibility.  
**Documentation**: See [trec_eval official documentation](https://github.com/usnistgov/trec_eval) for complete metric reference.

---

## Multi-Mode Benchmarking

The evaluation system supports batch benchmarking of all three retrieval modes (lexical-only, vector-only, hybrid) in a single operation. This enables systematic comparison of retrieval approaches using identical query sets and evaluation criteria.

### Benchmark Comparison Table (Template - Example Values)

| Metric | Lexical-Only | Vector-Only | Hybrid | Best Mode |
| --- | --- | --- | --- | --- |
| nDCG@10 | 0.32 | 0.28 | **0.38** | Hybrid |
| MAP@100 | 0.27 | 0.24 | **0.31** | Hybrid |
| MRR@10 | 0.45 | 0.42 | **0.52** | Hybrid |
| Recall@50 | 0.58 | 0.55 | **0.65** | Hybrid |
| Recall@100 | 0.63 | 0.60 | **0.72** | Hybrid |
| HitRate@10 | 0.73 | 0.70 | **0.81** | Hybrid |

### Performance Expectations

- **Hybrid retrieval** typically outperforms individual modes on most metrics by combining lexical precision with semantic recall
- **Lexical-only** excels on exact term matches and domain-specific terminology
- **Vector-only** performs well on semantic similarity and cross-domain queries
- **Mode selection** should consider query characteristics and latency requirements

**Note:** Performance varies by domain, query type, and collection size. Results based on internal MS MARCO v2.1 development subset benchmarks.

### Benchmark Workflow

1. Execute `benchmark run` with configuration specifying all three modes
2. System runs identical queries against lexical, vector, and hybrid retrieval
3. Generate individual evaluation reports for each mode
4. Create comparative analysis showing metric differences
5. Output structured `BenchmarkReport.json` and human-readable `BenchmarkComparison.md`

# Retrieval KPI Reference — TREC 2025 (R Task)

This note pulls together the metrics we track for retrieval experiments and clarifies which assets are currently available for evaluation.

---

## Evaluation Fundamentals

**Why multiple metrics matter:**
- **Precision vs Recall trade-offs**—more docs = higher recall, lower precision
- **Ranking order critical**—users examine top results first, so position matters
- **Graded relevance**—documents aren't just relevant/not relevant; they have degrees of usefulness
- **Different use cases**—QA systems need fast first hits, research systems need comprehensive coverage

**Test collection components:**
- **Documents** to search (MS MARCO v2.1 corpus with ≈113M segments)
- **Information needs** (queries/topics that represent real user questions)
- **Relevance judgements** (`qrels`) that indicate how well each document answers each query
- **Dev/test splits** prevent overfitting and ensure fair evaluation

**How metrics work together:**
- **nDCG@10**: Primary leaderboard metric—rewards early, high-quality hits
- **MAP@100**: Comprehensive ranking quality across full submission depth
- **MRR@10**: "First good answer" latency—critical for question-answering
- **Recall@K**: Coverage diagnostic—ensures we're not missing relevant content
- **HitRate@10**: Binary success check—did users find anything useful?

---

## 1. Data Packages & Files

The helper script `npm run pull:qrel` downloads all available TREC benchmarks into `.data/trec_rag_assets/`. The **TREC DL 2023 (rag23)** dataset is the default for evaluation. Override with flags: `npm run benchmark:lexical -- --24` (see `backend/eval/README.md` for all options).

### Available Benchmarks

| Benchmark | Topics File | Qrels File | Topics | Usage |
| --- | --- | --- | --- | --- |
| **rag23** (default) | `topics.dl23.txt` | `qrels.dl23-doc-msmarco-v2.1.txt` | 700 | Primary evaluation dataset |
| **rag24** | `topics.rag24.test.txt` | `qrels.rag24.test-umbrela-all.txt` | 301 | TREC RAG 2024 UMBRELA |
| **dl21** | `topics.dl21.txt` | `qrels.dl21-doc-msmarco-v2.1.txt` | 477 | TREC DL 2021 |
| **dl22** | `topics.dl22.txt` | `qrels.dl22-doc-msmarco-v2.1.txt` | 500 | TREC DL 2022 |
| **dl23** | `topics.dl23.txt` | `qrels.dl23-doc-msmarco-v2.1.txt` | 700 | TREC DL 2023 |
| **msmarco-dev** | `topics.msmarco-v2-doc.dev.txt` | `qrels.msmarco-v2.1-doc.dev.txt` | 4,552 | MS MARCO Dev |
| **msmarco-dev2** | `topics.msmarco-v2-doc.dev2.txt` | `qrels.msmarco-v2.1-doc.dev2.txt` | 5,000 | MS MARCO Dev2 |
| **rag25** | `trec_rag_2025_queries.jsonl` | *Pending* | - | 2025 topics (qrels TBD) |

All files are sourced from [TREC RAG 2025 Corpus](https://trec-rag.github.io/annoucements/2025-rag25-corpus/) via the `castorini/anserini-tools` repository.

### 2025 Track Baselines

| Asset | Purpose | Source |
| --- | --- | --- |
| **run.rankqwen3_32b.rag25.txt** | Organiser RankQwen3-32B baseline (top-100 TSV) | [castorini/ragnarok_data](https://github.com/castorini/ragnarok_data/tree/main/rag25/retrieve_results/MISC) |
| **retrieve_results_rankqwen3_32b.rag25_top100.jsonl** | Candidate payload for the baseline run | same as above |

---

## 2. Metric Summary (targets & trec_eval flags)

All retrieval KPIs depend on relevance judgements. The default evaluation uses **TREC DL 2023 (rag23)** qrels; override with flags: `npm run benchmark:lexical -- --24`. Target values are configured in `backend/eval/config.yaml` and justified using external baselines in **Section 7**.

**⚠️ Important:** These are **stretch research goals** for a well-engineered hybrid system (BM25 + dense + cross-encoder/LLM reranking), not baseline expectations. They represent "strong but not absolute SOTA" performance—achievable with serious engineering effort, but not expected from quick baselines.

| Metric | Computation | Stretch Target (2025) | Competitive Baseline | Notes |
| --- | --- | --- | --- | --- |
| nDCG@10 / 25 / 50 / 100 | `trec_eval` | 0.60 | ~0.50 | Primary leaderboard metric; graded relevance and position-sensitive. |
| MAP@100 | `trec_eval` | 0.35 | ~0.28–0.30 | Full-depth ranking quality up to 100 docs; balances precision and recall. |
| MRR@10 | `trec_eval` | 0.45 | ~0.35–0.40 | "First good answer" latency; focuses on earliest relevant hit in top 10. |
| Recall@25 / 50 / 100 | `trec_eval` | 0.70 (@25) / 0.78 (@50) / 0.85 (@100) | ~0.75 (@100) | Coverage of judged relevant documents at common cutoffs; @100 matches TREC cap. |
| HitRate@10 | Custom | 0.75 | ~0.65 | Share of queries with any relevant doc in top 10; simple binary success check. |

**Two-band framework:** Compare runs against both the **competitive baseline** (well-tuned BM25 + basic dense retrieval) and the **stretch target** (full hybrid + rerank stack). Early runs should aim for baseline; final system targets stretch goals.

See **Section 2.1** for historical DL22/DL23/RAG24 baselines and **Section 7** for how they map to these target numbers.

### 2.1 Multi-year leaderboard context (DL22–DL23, RAG24)

To ground these 2025 targets, we summarise representative **lexical baselines** and **top systems** for closely related large-scale tracks:

| Track & year | Corpus / qrels | Lexical baseline (NDCG@10) | Best system (NDCG@10) | Notes |
| --- | --- | --- | --- | --- |
| **TREC DL 2022 (doc)** | MS MARCO v2.1 documents, passage-derived qrels | ~0.34 (BM25-style baseline) | 0.76 (`NLE_SPLADE_RR_D`) | Values from Table 7 of the TREC 2022 Deep Learning overview (document ranking). [^6] |
| **TREC DL 2023 (doc)** | MS MARCO v2.1 documents, official DL23 qrels | 0.49 (`D_bm25_splades`) | 0.69 (`D_naverloo-frgpt4`) | Values from Table 3 of the TREC 2023 Deep Learning overview (document ranking). [^2] |
| **TREC RAG 2024 (R task)** | MS MARCO v2.1 segments, UMBRELA qrels | ~0.40–0.45 (BM25, est.) | ~0.55–0.65 (BM25→LLM rerank, est.) | Estimates based on the organisers' BM25→RankLLM pipelines and UMBRELA evaluation setup [^8] together with MS MARCO long-document benchmarks. [^9] Official retrieval leaderboard is not yet public. |

These ranges motivate setting our 2025 retrieval goals near the upper half of the DL23 band (for example, nDCG@10 ≈ 0.60) while remaining below the very best DL22 systems, and aiming for RAG-style nDCG@20/Recall@100 that substantially outperform pure BM25.

*Legend — `trec_eval` = official NIST tool [^4], falls back to `pytrec_eval` [^5] if binary unavailable.*

---

## 3. Metric Definitions

### 3.1 Normalized Discounted Cumulative Gain @ K (nDCG@K)

**What it measures:**
- **Ranking quality** considering both relevance grades and position
- **User attention modeling**—early ranks matter exponentially more than later ones
- **Graded relevance**—documents aren't just relevant/not relevant; they have degrees of usefulness

**How it's calculated:**
- **CG**: Sum relevance scores (ignores position)
- **DCG**: Add logarithmic discount $\frac{1}{\log_2(i+1)}$ for position $i$
- **NDCG**: Normalize by $\mathrm{IDCG}$ (perfect ranking) for fair comparison across queries

**Formula:** \(\mathrm{nDCG@K} = \frac{1}{\mathrm{IDCG@K}} \sum_{i=1}^{K} \frac{2^{\mathrm{rel}_i}-1}{\log_2(i+1)}\)

**Why it matters:**
- **Primary leaderboard metric** for TREC competitions
- **Discount factor** models real user behavior—position $1 \gg$ position $10$
- **Normalization** prevents queries with many relevant docs from inflating scores
- **When to prioritize:** Always—this is the main optimization target

### 3.2 Mean Average Precision @ 100 (MAP@100)

**What it measures:**
- **Comprehensive ranking quality** across the full submission depth (100 documents)
- **Precision-recall balance**—rewards systems that find relevant docs early AND comprehensively
- **Ranking sensitivity**—heavily penalizes systems that bury relevant docs lower in results

**How it's calculated:**
- **First average**: Calculate $\mathrm{AP}$ per query (average precision at each relevant doc)
- **Second average**: Mean $\mathrm{AP}$ scores across all queries
- **Double-averaging** ensures early relevant docs get higher scores
- **Cutoff at 100**: Only considers the top 100 retrieved documents per query, but denominator uses all relevant documents

**Formula:** \(\mathrm{MAP@100} = \frac{1}{|Q|} \sum_{q} \frac{1}{|\mathrm{Rel}_q|} \sum_{k=1}^{100} P_q(k)\cdot \mathrm{rel}_q(k)\)

**Why it matters:**
- **Standard metric** for comparing retrieval systems across domains
- **Balances precision/recall** across 100 ranks—not just top-10 performance
- **Ranking sensitive**—positions $1,2,4 \gg 2,5,6$ for same docs found
- **When to prioritize:** When you need comprehensive evaluation beyond just top results

### 3.3 Mean Reciprocal Rank @ 10 (MRR@10)

**What it measures:**
- **"First good answer" latency**—how quickly users find their first relevant result
- **Binary success per query**—ignores all subsequent relevant documents
- **User satisfaction proxy**—correlates with "did I find what I need?" experience

**How it's calculated:**
- Find **first relevant doc** rank $(1-10)$ per query
- Take **reciprocal** $\frac{1}{\mathrm{rank}}$ (or $0$ if none found)
- **Average** reciprocals across all queries

**Formula:** \(\mathrm{MRR@10} = \frac{1}{|Q|} \sum_{q} \frac{1}{\mathrm{rank}_q}\) where $\frac{1}{\mathrm{rank}_q} = 0$ if no relevant document is found in the top 10 (i.e., $\mathrm{rank}_q = 0$).

**Why it matters:**
- **QA systems**—users need just one good answer, not comprehensive coverage
- **Navigational queries**—finding specific page/site/document
- **Early-hit diagnostic**—complements MAP's comprehensive view with speed focus
- **When to prioritize:** Question-answering, fact-finding, and navigational use cases

### 3.4 Recall @ 25 / 50 / 100

**What it measures:**
- **Coverage diagnostic**—what fraction of all relevant docs did we find?
- **Comprehensiveness indicator**—ensures we're not missing important content
- **Pooling methodology connection**—relates to human annotation process

**How it's calculated:**
- Count **relevant docs** in top K per query
- Divide by **total relevant docs** for that query
- **Average** fraction across all queries

**Formula:** \(\mathrm{Recall@K} = \frac{1}{|Q|} \sum_{q} \frac{|\mathrm{Rel}_q \cap \mathrm{Retrieved}_{q,\le K}|}{|\mathrm{Rel}_q|}\)

**Why it matters:**
- **@100 aligns with TREC submission cap**—official constraint for competition
- **Computational efficiency**—@50 balances depth vs speed for development
- **System comparison**—shows if we find docs other systems consider relevant
- **When to prioritize:** Research systems, comprehensive information gathering, ensuring no important content is missed

### 3.5 Hit Rate @ 10 (HitRate@10)

**What it measures:**
- **Binary success rate**—any relevant doc in top 10?
- **User satisfaction proxy**—"did I find anything useful on the first page?"
- **Simple diagnostic**—ignores ranking quality, just hit/miss

**How it's calculated:**
- **Per query**: $1$ if any relevant doc in top $10$, else $0$
- **Average** binary outcomes across all queries
- **Simple percentage** of "successful" queries
- **Only queries with at least one relevant document** are included (standard IR practice, matching trec_eval behavior)

**Formula:** \(\mathrm{HitRate@10} = \frac{1}{|Q'|} \sum_{q \in Q'} \mathbf{1}[\mathrm{Rel}_q \cap \mathrm{Retrieved}_{q,\le 10} \neq \emptyset]\) where $Q' = \{q \in Q : |\mathrm{Rel}_q| > 0\}$ (only queries with at least one relevant document are included).

**Implementation:**
- Custom post-processing (not in `trec_eval` [^4])
- Uses rank field as authoritative (rank 1-10 = top 10, regardless of scores)
- Binary relevance: any document with relevance > 0 (grades 1 or 2) counts as relevant
- Deterministic tie-breaking: when building TREC runs, equal scores are sorted by doc_id for reproducible rankings

**Why it matters:**
- **Fast diagnostic**—"Did user find anything useful?"
- **Query success rate**—correlates with user satisfaction
- **Ignores ranking quality**—just binary hit/miss, useful for debugging
- **When to prioritize:** Quick sanity checks, user experience validation, debugging retrieval failures

---

## Interpreting Results

### Reading the Metric Summary Table

The metric summary table (Section 2) provides the **current 2025 targets** and the **metrics we optimise**. When interpreting deltas:

- **nDCG@10**: +0.05 is a meaningful improvement, +0.10 is substantial.
- **MAP@100**: +0.03–0.05 uplift is typically substantial.
- **MRR@10**: +0.10 usually indicates clearly better first-hit behaviour.
- **Recall@50**: +0.05–0.10 suggests better coverage.
- **HitRate@10**: +0.05–0.10 means fewer “zero-result” queries.

### Common Pitfalls and Gotchas

- **Pooling bias**: Recall metrics depend on annotation depth—shallow pools inflate scores
- **Query difficulty**: Some queries have no relevant docs—check HitRate@10 first
- **Score ties**: Ensure deterministic ranking for tied scores to avoid trec_eval warnings
- **Cutoff effects**: nDCG@10 vs nDCG@100 can tell different stories about ranking quality

### Balancing Multiple Objectives

- **Primary focus**: nDCG@10 (leaderboard metric)
- **Comprehensive check**: MAP@100 (full-depth ranking)
- **Speed validation**: MRR@10 (first-hit performance)
- **Coverage check**: Recall@50/100 (comprehensiveness)
- **Sanity check**: HitRate@10 (basic success rate)

---

## 4. Computing KPIs

1. **Generate a valid run**  
   - Output six-column TREC TSV (`topic Q0 docid rank score runid`) with ≤100 hits per query.
   - Deterministic tie-breaking: segments sorted by score (desc), then doc_id (asc) before assigning ranks to ensure reproducible evaluation.

2. **Evaluate with trec_eval**  
   ```bash
   trec_eval -c \
     -m ndcg_cut.10 -m ndcg_cut.25 -m ndcg_cut.50 -m ndcg_cut.100 \
     -m map_cut.100 \
     -m recip_rank -m recip_rank.10 \
     -m recall.25 -m recall.50 -m recall.100 \
     /path/to/qrels.txt \
     /path/to/run.tsv
   ```
   - Default: `qrels.dl23-doc-msmarco-v2.1.txt` (rag23). Override benchmark via npm flags.
   - Falls back to `pytrec_eval` [^5] if `trec_eval` [^4] binary unavailable.

3. **Compute HitRate@10**  
   - Custom post-processing: for each query with at least one relevant document, check if any top-10 doc IDs (by rank) have relevance > 0 in qrels.
   - Only queries with relevant documents are included in the calculation (matching trec_eval behavior).

4. **Log experiment metadata**  
   - Capture run ID, config hash, index snapshot, timestamp, and metric outputs.

---

## 5. File Glossary

All files are stored in `.data/trec_rag_assets/` and downloaded via `npm run pull:qrel`.

### Topics Files
- `topics.dl23.txt` — TREC DL 2023 (700 queries, default)
- `topics.rag24.test.txt` — TREC RAG 2024 (301 queries)
- `topics.dl21.txt` — TREC DL 2021 (477 queries)
- `topics.dl22.txt` — TREC DL 2022 (500 queries)
- `topics.msmarco-v2-doc.dev.txt` — MS MARCO Dev (4,552 queries)
- `topics.msmarco-v2-doc.dev2.txt` — MS MARCO Dev2 (5,000 queries)
- `trec_rag_2025_queries.jsonl` — TREC RAG 2025 (qrels pending)

### Qrels Files
- `qrels.dl23-doc-msmarco-v2.1.txt` — TREC DL 2023 (default)
- `qrels.rag24.test-umbrela-all.txt` — TREC RAG 2024
- `qrels.dl21-doc-msmarco-v2.1.txt` — TREC DL 2021
- `qrels.dl22-doc-msmarco-v2.1.txt` — TREC DL 2022
- `qrels.msmarco-v2.1-doc.dev.txt` — MS MARCO Dev
- `qrels.msmarco-v2.1-doc.dev2.txt` — MS MARCO Dev2

### 2025 Baselines
- `run.rankqwen3_32b.rag25.txt` — Organiser RankQwen baseline run
- `retrieve_results_rankqwen3_32b.rag25_top100.jsonl` — Baseline candidate payload

---

## 6. Multi-Mode Benchmarking

### Retrieval Approaches Explained

**Lexical-Only (BM25, etc.)**
- **How it works**: Exact term matching with TF-IDF-style weighting.
- **Strengths**: Precise on exact terminology, domain-specific vocabulary, fast.
- **Weaknesses**: Misses semantic similarity, synonyms, paraphrases.
- **When to use**: Technical documentation, code search, exact phrase queries.

**Vector-Only (Dense embeddings)**
- **How it works**: Semantic similarity in embedding space.
- **Strengths**: Handles synonyms, paraphrases, cross-domain concepts.
- **Weaknesses**: Can miss exact matches, domain-specific terms.
- **When to use**: Question-answering, semantic search, cross-lingual tasks.

**Hybrid (Lexical + Vector)**
- **How it works**: Combines both approaches with learned or heuristic fusion.
- **Strengths**: Best of both worlds—precision and recall.
- **Weaknesses**: More complex, higher computational cost.
- **When to use**: Production systems when you need comprehensive coverage.



## 7. Why these targets? (DL22/DL23/RAG24 context)

This section explains how we chose the 2025 targets in the **Metric Summary** table (Section 2), using the baselines in **Section 2.1** and the references below.

- **nDCG@10 and MAP@100 (ranking quality)** — Section 2.1 shows that on MS MARCO v2.1 documents, BM25-style runs achieve NDCG@10≈0.34–0.49 while the best DL22–DL23 systems reach ≈0.69–0.76 with AP≈0.35–0.42. [^2][^6] We therefore set **nDCG@10=0.60** and **MAP@100=0.35** roughly midway between strong BM25 and state-of-the-art, rather than targeting only the very top runs. Target (0.60) is very close to the strong neural-reranker (0.596) from DL23, representing a well-tuned hybrid + cross-encoder pipeline.
- **MRR@10 (first relevant hit)** — The MS MARCO Document leaderboard reports top MRR@100≈0.45–0.51 for widely reproduced neural systems such as `coCondenser(maxp)+MORES+`, with lexical methods around 0.20. [^7] Our **MRR@10=0.45** target matches this "strong but realistic" band. This assumes you almost always get a relevant item into the top 3–5 for queries with judged relevant documents—ambitious but achievable for a well-engineered hybrid + LLM rerank pipeline.
- **Recall@K (coverage)** — DGR on TREC DL 2019 achieves Recall@20=0.676 and Recall@100=0.865. [^3] We choose **Recall@25/50/100 = 0.70/0.78/0.85** as slightly conservative versions of these numbers to account for differences between DL19, DL23, and our RAG-style evaluation, while still aiming for high coverage. These are deliberately placed just below DGR's strong generative retrieval system.
- **Consistency with RAG-style retrieval** — For the TREC RAG 2024 track, organisers define nDCG@20/100 and Recall@100 with UMBRELA qrels and provide BM25→LLM baselines. [^8] Combined with long-document MS MARCO studies [^9], these suggest segments-level BM25 and reranked runs fall into bands consistent with our chosen targets. **Important caveat:** All deep TREC numbers cited are mainly doc-level (DL22/23), while TREC RAG uses segments. Per-metric behavior may differ slightly, but good BM25→rerank pipelines on segments can reach nDCG/Recall levels close to the target band.

**Target interpretation:** These are **stretch research goals** for a well-engineered hybrid system (BM25 + dense + cross-encoder/LLM reranking), not baseline expectations. They require: well-tuned hybrid retriever, strong cross-encoder/LLM reranker, and solid engineering (deduping, segmenting, good tie-breaking). Pure BM25 or simple baselines will not reach these targets.

Treat these targets as **global 2025 research goals** (not hard per-experiment thresholds). As RAG 2024/2025 white papers and official leaderboards become available, we can revisit this section and, if needed, tighten the numbers in Section 2.

---

[^1]: TREC 2025 RAG timeline (11 July: topics, 23 July: baselines, October: results & judgements). <https://trec-rag.github.io/annoucements/2025-timeline/>

[^2]: **TREC 2023 Deep Learning Track (Document Ranking)** — Craswell et al. (2023). Overview of the TREC 2023 Deep Learning Track. <https://trec.nist.gov/pubs/trec32/papers/Overview_deep.pdf>. Table 3 reports document ranking results: BM25 baseline (`D_bm25_splades`): nDCG@10=0.494, nDCG@100=0.515, AP=0.298. Best system (`D_naverloo-frgpt4`, h2oloo group): nDCG@10=0.689, nDCG@100=0.635, AP=0.419. Strong neural-reranker (`D_naverloo_bm_splade_RR`): nDCG@10=0.596, AP=0.379.

[^3]: **Competitive Recall Benchmarks** — DGR (Distillation Enhanced Generative Retrieval) on TREC DL 2019: Recall@5=0.429, Recall@20=0.676, Recall@100=0.865. [Paper](https://aclanthology.org/2024.findings-acl.662.pdf), Table 2. DL19 and DL23 are similar tracks with comparable evaluation methodology, so these values provide a reasonable upper bound. Recall targets are interpolated as @25=0.70, @50=0.78, @100=0.85 (slightly conservative relative to DGR's 0.865 to account for dataset differences).

[^4]: Official NIST trec_eval tool: <https://github.com/usnistgov/trec_eval>

[^5]: Python implementation of trec_eval: <https://github.com/cvangysel/pytrec_eval>

[^6]: **TREC 2022 Deep Learning Track (Document Ranking)** — Craswell et al. (2022). Overview of the TREC 2022 Deep Learning Track. <https://trec.nist.gov/pubs/trec31/papers/Overview_deep.pdf>. Table 7 reports document ranking: BM25-style baselines (e.g., `uogtr_doc_dph`, `srchvrs` traditional runs) achieve NDCG@10≈0.34–0.36, while the best system (`NLE_SPLADE_RR_D`) achieves NDCG@10=0.7611, NCG@100=0.5787, AP=0.3453. We use these to bracket realistic lower/upper bounds for MS MARCO v2.1 document retrieval in 2022.

[^7]: **MS MARCO Document Ranking Leaderboard** — public leaderboard at <https://microsoft.github.io/MSMARCO-Document-Ranking-Submissions/leaderboard/>. As of 2022-02-08, the top entry `coCondenser(maxp) + MORES+` reports MRR@100 (Dev)=0.512 and MRR@100 (Eval)=0.446, while lexical baselines such as `Anserini BM25` and `IndriQueryLikelihood` are around 0.20. Our MRR@10 target is chosen to be consistent with these strong-but-achievable systems.

[^8]: **TREC 2024 RAG Baselines & UMBRELA qrels** — official RAG track announcements describing baseline BM25→RankLLM pipelines and the release of UMBRELA-based qrels and evaluation commands. See "TREC 2024 RAG Baselines, validator script, and submissions open" and "TREC 2024 RAG UMBRELA Qrels Released" on <https://trec-rag.github.io>. For baseline implementations, see also: Thakur et al. (2024). "Ragnarok: A Reusable RAG Framework and Baselines for TREC 2024 RAG Track." In *ECIR 2025*. <https://dl.acm.org/doi/abs/10.1007/978-3-031-88708-6_9>. These define nDCG@20, nDCG@100, and Recall@100 as primary retrieval metrics for RAG 2024.

[^9]: **Long-document & MS MARCO benchmarks** — Boytsov et al. (2024). *Positional Bias in Long-Document Ranking: Impact, Assessment, and Mitigation.* <https://arxiv.org/abs/2207.01262>. Their BM25 and FirstP/MaxP results on MS MARCO documents and TREC DL (for example, BM25 MRR≈0.27, TREC DL NDCG@10≈0.54–0.66) support the approximate ranges we use when transferring expectations to RAG-style MS MARCO v2.1 segment retrieval.

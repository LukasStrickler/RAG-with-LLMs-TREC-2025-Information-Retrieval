# Retrieval KPI Reference — TREC 2025 (R Task)

This note pulls together the metrics we track for retrieval experiments and clarifies which
assets are currently available for evaluation. It reflects the latest organiser releases
as of October 2025 and mirrors the structure used in `KPI-PLAN.md`.

---

## Evaluation Fundamentals

**Why multiple metrics matter:**
- **Precision vs Recall trade-offs**—more docs = higher recall, lower precision
- **Ranking order critical**—users examine top results first, so position matters
- **Graded relevance**—documents aren't just relevant/not relevant; they have degrees of usefulness
- **Different use cases**—QA systems need fast first hits, research systems need comprehensive coverage

**Test collection components:**
- **Documents** to search (MS MARCO v2.1 corpus with 120M+ segments)
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

The helper script `npm run pull:qrel -- --force` downloads the artefacts listed below into
`.data/trec_rag_assets/`. Use the 2025 bundle for smoke-testing the current track and the
2024 bundle for KPI-driven iteration until the official 2025 relevance judgements ship.

### 2025 Track (official narratives & baselines)

| Asset | Purpose | Source | Local Path |
| --- | --- | --- | --- |
| **trec_rag_2025_queries.jsonl** | Official 2025 dev/test topics | [TREC RAG – Topics Released](https://trec-rag.github.io/annoucements/2025-topics-released/) | `.data/trec_rag_assets/trec_rag_2025_queries.jsonl` |
| **run.rankqwen3_32b.rag25.txt** | Organiser RankQwen3-32B baseline (top-100 TSV) | [castorini/ragnarok_data · rag25](https://github.com/castorini/ragnarok_data/tree/main/rag25/retrieve_results/MISC) | `.data/trec_rag_assets/run.rankqwen3_32b.rag25.txt` |
| **retrieve_results_rankqwen3_32b.rag25_top100.jsonl** | Candidate payload for the baseline run | same as above | `.data/trec_rag_assets/retrieve_results_rankqwen3_32b.rag25_top100.jsonl` |
| **qrels.rag25.*.txt** | * *Pending.* The organisers’ timeline states that official TREC 2025 RAG judgements will be returned to participants in October 2025. [^1] |

### 2024 Rehearsal Bundle (available now)

| Asset | Purpose | Source | Local Path |
| --- | --- | --- | --- |
| **topics.rag24.test.txt** | TREC 2024 test topics, aligned with UMBRELA qrels | [TREC RAG 2024 Topics](https://trec-rag.github.io/assets/txt/topics.rag24.test.txt) | `.data/trec_rag_assets/topics.rag24.test.txt` |
| **qrels.rag24.test-umbrela-all.txt** | Publicly released UMBRELA relevance judgements | [TREC RAG UMBRELA release](https://trec-rag.github.io/annoucements/umbrela-qrels/) | `.data/trec_rag_assets/qrels.rag24.test-umbrela-all.txt` |
| **fs4_bm25+…rag24.test.txt** | Organiser BM25+rerank baseline (top-100 TSV) | [castorini/ragnarok_data · rag24](https://github.com/castorini/ragnarok_data/tree/main/rag24/retrieve_results/RANK_ZEPHYR) | `.data/trec_rag_assets/fs4_bm25+rocchio_snowael_snowaem_gtel+monot5_rrf+rz_rrf.rag24.test.txt` |
| **retrieve_results_fs4_…rag24.test_top100.jsonl** | Candidate payload for the same baseline | same as above | `.data/trec_rag_assets/retrieve_results_fs4_bm25+rocchio_snowael_snowaem_gtel+monot5_rrf+rz_rrf.rag24.test_top100.jsonl` |

**How to use these bundles**
- **2025**: validate run formatting, compare against RankQwen outputs, and be ready to re-score as soon as the official qrels appear.
- **2024**: run full KPI evaluations today—the UMBRELA qrels provide honest nDCG/MAP/recall numbers for iterative development.

---

## 2. Metric Summary (targets & trec_eval flags)

All retrieval KPIs depend on relevance judgements. As of October 2025 the UMBRELA qrels (2024) are the only public labels, so they drive the “✅” column in the table below.

| Metric | trec_eval Flag(s) | Typical BM25 Baseline | Competitive Target | Currently Evaluable (Oct 2025) | Notes |
| --- | --- | --- | --- | --- | --- |
| nDCG@10 / 25 / 50 / 100 | `-m ndcg_cut.10` etc. | ~0.30–0.32 (at @10) | ≥0.35 good / ≥0.40 strong | ✅ 2024 UMBRELA<br>🔒 2025 | Primary leaderboard signal; rewards early, graded hits. |
| MAP@100 | `-m map_cut.100` | ~0.25–0.27 | +0.03–0.05 uplift | ✅ 2024 UMBRELA<br>🔒 2025 | Balances precision and recall across the full submission depth. |
| MRR@10 | `-m recip_rank` (or `recip_rank.cut.10`) | ~0.45 | ≥0.55 | ✅ 2024 UMBRELA<br>🔒 2025 | Captures “first relevant” latency; ideal for QA-style queries. |
| Recall@25 / 50 / 100 | `-m recall.25` etc. | ~0.55–0.60 (@50) | ≥0.62 (@50) | ✅ 2024 UMBRELA<br>🔒 2025 | Measures coverage; @100 aligns with TREC’s 100-doc cap. |
| HitRate@10 | Post-processing | ~0.70–0.75 | ≥0.80 | ✅ 2024 UMBRELA<br>🔒 2025 | Binary success in the top 10—fast sanity check. |

*Legend — ✅: can be measured today against `qrels.rag24.test-umbrela-all.txt`; 🔒: depends on the forthcoming 2025 judgements.*

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

**Formula:** \(\mathrm{MAP@100} = \frac{1}{|Q|} \sum_{q} \frac{1}{\min(|\mathrm{Rel}_q|,100)} \sum_{k=1}^{100} P_q(k)\cdot \mathrm{rel}_q(k)\)

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

**Formula:** \(\mathrm{MRR@10} = \frac{1}{|Q|} \sum_{q} \frac{1}{\mathrm{rank}_q}\) with \(\mathrm{rank}_q=0\) if no relevant is found in the top 10.

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

**Formula:** \(\mathrm{HitRate@10} = \frac{1}{|Q|} \sum_{q} \mathbf{1}[\mathrm{Rel}_q \cap \mathrm{Retrieved}_{q,\le 10} \neq \emptyset]\)

**Why it matters:**
- **Fast diagnostic**—"Did user find anything useful?"
- **Query success rate**—correlates with user satisfaction
- **Ignores ranking quality**—just binary hit/miss, useful for debugging
- **When to prioritize:** Quick sanity checks, user experience validation, debugging retrieval failures

---

## Interpreting Results

### Reading the Metric Summary Table

The metric summary table (Section 2) provides targets and context for interpreting your results:

- **✅ Currently Evaluable**: Can be measured today against 2024 UMBRELA qrels
- **🔒 2025**: Depends on forthcoming official judgements
- **Typical BM25 Baseline**: What to expect from basic lexical retrieval
- **Competitive Target**: What constitutes meaningful improvement

### What Constitutes a Meaningful Improvement

- **nDCG@10**: +0.05 is significant, +0.10 is substantial
- **MAP@100**: +0.03–0.05 uplift is meaningful
- **MRR@10**: +0.10 improvement indicates better first-hit performance
- **Recall@50**: +0.05–0.10 shows better coverage
- **HitRate@10**: +0.05–0.10 indicates fewer "zero-result" queries

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
   - Keep ordering deterministic for tied scores to avoid trec_eval warnings.
2. **Evaluate with trec_eval**  
   ```bash
   trec_eval -c \
     -m ndcg_cut.10 -m ndcg_cut.25 -m ndcg_cut.50 -m ndcg_cut.100 \
     -m map_cut.100 \
     -m recip_rank -m recip_rank.cut.10 \
     -m recall.25 -m recall.50 -m recall.100 \
     /path/to/qrels.txt \
     /path/to/run.tsv
   ```
   - Use `qrels.rag24.test-umbrela-all.txt` for rehearsal scoring; swap in the official 2025 qrels when released.
3. **Compute HitRate@10**  
   - Simple post-processing: for each query, check whether any of the top-10 doc IDs appear with a positive grade in the qrels.
4. **Log experiment metadata**  
   - Capture run ID, config hash, index snapshot, timestamp, and metric outputs so numbers can be regenerated when the 2025 qrels arrive.

---

## 5. File Glossary

- `.data/trec_rag_assets/trec_rag_2025_queries.jsonl` — official 2025 topic narratives.  
- `.data/trec_rag_assets/run.rankqwen3_32b.rag25.txt` — organiser RankQwen baseline run.  
- `.data/trec_rag_assets/retrieve_results_rankqwen3_32b.rag25_top100.jsonl` — candidate payload for the RankQwen run.  
- `.data/trec_rag_assets/topics.rag24.test.txt` — 2024 topics aligned with UMBRELA qrels.  
- `.data/trec_rag_assets/qrels.rag24.test-umbrela-all.txt` — 2024 UMBRELA relevance judgements.  
- `.data/trec_rag_assets/fs4_bm25+…rag24.test.txt` — strong 2024 retrieval baseline run.  
- `.data/trec_rag_assets/retrieve_results_fs4_…rag24.test_top100.jsonl` — candidate payload for the 2024 baseline run.

---

## 6. Multi-Mode Benchmarking

### Retrieval Approaches Explained

**Lexical-Only (BM25, etc.)**
- **How it works**: Exact term matching with TF-IDF weighting
- **Strengths**: Precise on exact terminology, domain-specific vocabulary, fast
- **Weaknesses**: Misses semantic similarity, synonyms, paraphrases
- **When to use**: Technical documentation, code search, exact phrase queries

**Vector-Only (Dense embeddings)**
- **How it works**: Semantic similarity in embedding space
- **Strengths**: Handles synonyms, paraphrases, cross-domain concepts
- **Weaknesses**: Can miss exact matches, domain-specific terms
- **When to use**: Question-answering, semantic search, cross-lingual tasks

**Hybrid (Lexical + Vector)**
- **How it works**: Combines both approaches with learned fusion
- **Strengths**: Best of both worlds—precision AND recall
- **Weaknesses**: More complex, higher computational cost
- **When to use**: Production systems, when you need comprehensive coverage

### Performance Expectations

Based on internal benchmarks and TREC results:

| Mode | nDCG@10 | MAP@100 | MRR@10 | Recall@50 | Best For |
|------|---------|---------|--------|-----------|----------|
| **Lexical** | ~0.30–0.32 | ~0.25–0.27 | ~0.45 | ~0.55–0.60 | Exact matches, technical docs |
| **Vector** | ~0.28–0.30 | ~0.24–0.26 | ~0.42 | ~0.55–0.58 | Semantic similarity, QA |
| **Hybrid** | **~0.35–0.40** | **~0.28–0.32** | **~0.50–0.55** | **~0.60–0.65** | Production systems |

### Benchmarking Strategy

**Current (2024 UMBRELA qrels):**
- Use 2024 bundle for quantitative iteration and mode comparison
- Establish baselines for lexical, vector, and hybrid approaches
- Optimize hyperparameters and fusion strategies

**Future (2025 official qrels):**
- Re-score all historical experiments on identical qrels
- Anchor dashboards with organiser baselines (2024 FS4, 2025 RankQwen)
- Report improvements on official evaluation set

**Implementation:**
- Run identical queries against all three retrieval modes
- Generate comparative analysis showing metric differences
- Track trends across different query types and difficulty levels


[^1]: TREC 2025 RAG timeline (11 July: topics, 23 July: baselines, October: results & judgements). <https://trec-rag.github.io/annoucements/2025-timeline/>

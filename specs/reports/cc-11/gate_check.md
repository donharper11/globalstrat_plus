# CC-11 Gate Check — RAG Content Migration & SC Corpus Ingestion

**Spec:** `specs/CC-11-rag-content-migration.md` · **Observes:** `STANDING-DISCIPLINE.md`
**Status:** **HALTED at §2 Gate — curated corpus absent.** No content ingested, none fabricated.

---

## Gate verification (spec §2)

| Gate condition | Result | Detail |
|---|---|---|
| Target collection `globalstrat_plus_articles` exists | ✅ | Qdrant `192.168.50.186:6333`; vector size **384**, distance **Cosine**; **points = 0** (empty, ready to populate). |
| Inherited source collection exists | ✅ | `globalstrat_articles`; size 384, Cosine; **points = 2336** (available for the strategy re-ingest in §3.1). |
| Curated corpus under `rag_sources/staging/` (or an explicitly approved path), ≥ 40 reviewed items | ❌ | **No `rag_sources/` directory anywhere** in the repo or `~`. No `staging/`, `curated/`, or corpus store found. `backend/core/rag/` contains only pipeline code (`ingest.py`, `embeddings.py`, `client.py`, `views.py`), not article content. **0 reviewed items → below the 40-item threshold.** |

Qdrant collections present on the server (context): `globalstrat_articles`, `globalstrat_plus_articles`, plus unrelated corpora (`aib_7c_materials`, `mis_textbook`, `becsr_textbook`, `research_papers`, …).

Per spec §2: *"If the curated corpus is absent or below 40 reviewed items, halt and report. Do not invent article content."* — and STANDING-DISCIPLINE §2/§3/§7. Execution is therefore halted.

```
MISMATCH DETECTED
Spec reference: §2 Gate — curated corpus exists under rag_sources/staging/ (or approved path), >= 40 reviewed items
Actual state:   No rag_sources/ path exists; 0 curated SC items present
Location:       /home/ubuntu/projects/globalstrat+/  (no rag_sources/staging/)
Proposed action: Provide the reviewed SC corpus (>=40 items) at rag_sources/staging/
                 or name an explicitly approved path; then CC-11 can execute.
Halting for review.
```

## What is ready (so execution is fast once the corpus lands)

- **Ingest pipeline** (`core/rag/ingest.py`): `ingest_article(filepath, catalog_entry, client, collection_name)` extracts text from PDF/DOCX/text, chunks (`chunk_article`, ~1500 chars / 200 overlap), embeds via `core.rag.embeddings.get_embedding` (`settings.EMBEDDING_MODEL`, 384-dim), and upserts to Qdrant with a payload carrying title/folder/tags. `assign_tags()` keyword-tags content.
- **Expected corpus shape:** a directory of source files + catalog entries (`relative_path`, `filename`, `title`, tags). The CC-11 `payload.topic` tags required are: `strategy` (inherited), and `supply_chain`, `trade_finance`, `compliance`, `logistics`, `resilience`, `chinese_institutional` (new SC content).

## Remaining work once un-gated (spec §3)

1. Re-ingest / snapshot-restore inherited strategy content into `globalstrat_plus_articles` with `payload.topic = strategy` (source `globalstrat_articles` has 2336 points).
2. Ingest the reviewed SC corpus with the topic tags above.
3. Run per-topic validation queries; record counts + samples.
4. Complete this report with collection config, counts, sample queries, and the source path.

## Decision required from the spec author / user

CC-11 cannot be completed without the curated corpus. Options: (a) supply the reviewed SC corpus (≥40 items) and name its path; (b) authorize the **inherited-strategy migration only** (§3.1) as a partial step — feasible now, but leaves SC ingestion and per-topic acceptance (§4.1/§4.3) still gated; (c) defer CC-11 until the corpus is curated.

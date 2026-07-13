# CC-11 (partial) — RAG corpus ingestion, first batch

**Rework follow-on (enrichment).** Loaded the user's first article batch into the
`globalstrat_plus_articles` Qdrant collection via the existing `ingest_articles`
pipeline, with content-based topic/tag curation.

## What was loaded
- **Source:** `docs/rag_sources/staging/` (27 PDFs; general supply chain, global
  sourcing, international marketing/strategy, political risk). The PDFs are
  gitignored (52 MB, third-party); the manifest `docs/rag_sources/catalog.json`
  is committed.
- **Result:** `python3 manage.py ingest_articles --source … --catalog … --reset`
  → **26 processed, 1 skipped, 475 chunks** in `globalstrat_plus_articles`
  (was empty). RAG auto-enabled for the active scenario (Consumer Electronics
  2026: `rag_enabled=true`, `max_research_queries_per_round=5`).
- **Skipped:** `article_Globalization of Markets by Ghemawat.pdf` — image-only
  PDF, no extractable text (needs OCR to ingest). Its globalization content
  overlaps other ingested pieces.

## Curation (this batch)
Each article's opening (title + abstract/intro) was scanned to assign a single
primary `topic` plus `tags`. The pipeline was extended so the payload carries a
`topic` field and merges curated catalog tags with keyword auto-tags:
- `core/rag/ingest.py`: added SC-specific tag rules (`global_sourcing`,
  `logistics`, `trade_finance`, `compliance`, `resilience`,
  `chinese_institutional`); `ingest_article` now merges `catalog.tags` with
  auto-tags and writes a `topic` to the Qdrant payload.

**Topic distribution (chunks):** resilience 100, strategy 95, market_entry 60,
supply_chain 44, culture 40, chinese_institutional 32, country_selection 26,
international_marketing 25, political_risk 14, trade_policy 14, global_sourcing 10,
emerging_market 8, trade_finance 6, globalization 1.

## Verification (semantic retrieval)
Real queries return the right articles:
- "currency hedging to protect an exporter from FX risk" → *How to Use Currency
  Hedging…* (score 0.80).
- "supply chain disruption and resilience risk" → *WEF Global Risks Report 2021*.
- "global sourcing supplier selection strategy" → *Understanding Integrated
  Global Sourcing* (0.72).

## Where this helps (unchanged from analysis)
RAG feeds strategic coherence scoring, team briefings, and communication
evaluation (Phase 2 / async) + a student research surface — it enriches the
narrative/coaching layer, not the Phase-1 deterministic numbers. No server reload
needed (runtime `search_articles` reads Qdrant directly).

## Follow-on (not done here)
- OCR + ingest the 1 skipped image-PDF if wanted.
- Corpus is 26 articles; the CC-11 plan target was 80–120 SC articles — add more
  batches over time (this pipeline handles them; re-run without `--reset` to
  append).
- Optional: snapshot-restore the parent `globalstrat_articles` (143 strategy
  articles) if the general-strategy corpus is wanted alongside.
- CC-17 (LLM narratives) is where this corpus produces rich SC event/compliance
  narratives — still un-built.

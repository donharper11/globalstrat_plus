# CC-11: RAG Content Migration and Supply Chain Corpus Ingestion

**Project:** globalstrat+  
**Spec Type:** Build pipeline - content/RAG  
**Depends on:** CC-1 Qdrant setup, curated corpus availability  
**Observes:** `STANDING-DISCIPLINE.md`  
**Status:** Drafted as gated handoff

---

## Non-Negotiable Builder Discipline

This bundle inherits `STANDING-DISCIPLINE.md`, but the following rules are repeated here because they are completion blockers:

1. Verify every existing field, model, table, endpoint, route, component, settings key, and payload shape before referencing it. Use the current codebase and database, not memory or nearby names.
2. Do not invent field names, model names, endpoint paths, YAML keys, payload keys, CSS classes, or React component names. If the expected name does not exist, halt with a MISMATCH report.
3. Do not silently adapt the spec to whatever name seems convenient. Report the actual state and wait for instruction if the contract and implementation diverge.
4. Before calling the bundle complete, self-verify every acceptance criterion with recorded command output, API/browser evidence, and a closeout report under the bundle's `specs/reports/cc-XX/` directory.
5. A passing backend response alone is not proof of frontend completion. Frontend bundles require browser verification of the actual user workflow.

---

## 1. Purpose

Populate `globalstrat_plus_articles` with inherited strategy content and new supply-chain content. This is not on the minimum UI E2E path, but it is required before SC narrative and advisory quality can be considered complete.

---

## 2. Gate

Before executing, verify that Qdrant collection `globalstrat_plus_articles` exists, the source collection for inherited GlobalStrat articles exists, and the curated corpus exists under `rag_sources/staging/` or another explicitly approved path.

If the curated corpus is absent or below 40 reviewed items, halt and report. Do not invent article content.

---

## 3. Required Work

1. Snapshot/restore or re-ingest inherited GlobalStrat strategy content with `payload.topic = strategy`.
2. Ingest reviewed SC content with topic tags: supply_chain, trade_finance, compliance, logistics, resilience, chinese_institutional.
3. Run validation queries for each topic.
4. Record source counts and query samples.

---

## 4. Acceptance Criteria

1. Qdrant collection contains inherited strategy content and SC content.
2. Every ingested item has topic metadata.
3. Validation queries return relevant results for each topic.
4. `specs/reports/cc-11/acceptance_report.md` records collection config, counts, sample queries, and source path.

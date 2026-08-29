# GlobalStrat+: REQUIRED READING

**Before starting any gap-closing work, read these documents in order:**

1. **Platform Governance & Discipline**
   - Read: `/home/ubuntu/projects/globalstrat+/specs/STANDING-DISCIPLINE.md`
   - Covers: Binding rules for all development
   
2. **Deployment Architecture**
   - Read: `/home/ubuntu/projects/globalstrat+/docs/DEPLOYMENT.md`
   - Covers: Frontend (ECS), Backend (VM .5), database, FRP tunnel configuration
   
3. **Backend Code Organization**
   - Read: `/home/ubuntu/projects/globalstrat+/backend/core/engine/` README (if exists)
   - Covers: Performance engine, Bass engine, compliance logic
   
4. **Handoff Overview**
   - Read: `/home/ubuntu/projects/globalstrat+/handoffs_v3/README.md`
   - Covers: All 11 completed fix cycles, current readiness state
   
5. **The Gap-Closing Report**
   - Read: `/home/ubuntu/projects/globalstrat+/gap_closing/5_globalstrat_plus_gap_closing.md`
   - Covers: 1 blocking finding (Vertex anomaly), 2 verification items, post-launch work

---

## Key Principles (from STANDING-DISCIPLINE)

- **All changes** must reference a spec/requirement
- **Testing** before merge (no guessing on complex logic)
- **Audit trail** in commits and handoff docs
- **Performance Index** is business-critical; changes require verification on fresh game

---

## Current Status

- **Round 1 readiness:** 11 fix cycles MERGED and DEPLOYED
- **Live site:** https://globalstrat.camdani.com
- **Blocker:** Vertex scoring anomaly (R1-09-F1) — must investigate and fix
- **Backend:** Running on .5 VM, port 8002
- **Database:** PostgreSQL on .38

---

## Do Not Skip These

1. **Do NOT deploy changes** without fresh-game verification
2. **Do NOT ignore Vertex anomaly** — credibility depends on fix
3. **Do NOT merge to main** without testing on actual game engine

---

**Time to read:** ~20 minutes  
**Then:** Open gap_closing/5_globalstrat_plus_gap_closing.md and follow §2 (items 1–3)

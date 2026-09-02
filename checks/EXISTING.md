# Pre-existing machinery in `globalstrat+`

## Pre-existing check machinery

Inventoried 2026-09-02 before aide-checks was installed. Nothing
listed here was removed, disabled, rewritten or weakened.

### Git hooks
- `core.hooksPath`: not set (default .git/hooks)
- none

### CI workflows
- `.github/workflows/frontend.yml`

### Committed validators, guards and quality runners
- `backend/core/management/commands/check_qdrant.py`
- `backend/core/management/commands/check_round_deadlines.py`
- `backend/core/management/commands/verify_audit_chain.py`
- `backend/core/management/commands/verify_scenario_schema.py`
- `handoff_readiness_v2/evidence/adversarial-balance/harness/checksums.py`

### Lint configuration
- none

### npm scripts that look like gates
- `frontend/globalstrat-frontend/package.json`
  - `test`: `react-scripts test`

### Deploy scripts
- `frontend/deploy-frontend.sh`

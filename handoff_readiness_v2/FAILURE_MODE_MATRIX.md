# Failure-mode matrix

| Scenario | Behaviour / recovery | Gate |
|---|---|---|
| DB loss mid-resolution | Atomic Phase 1 rolls back; FAILED is attempted after rollback but cannot persist while DB stays unavailable. Restore connectivity, inspect logs, use guarded recovery. | Injection pending |
| Backend restart | Phase-1 transaction rolls back. Phase-2 daemon work is lost and has no durable retry. | V2-006 P1; blocked |
| LLM timeout/error | Phase 1 is already committed; batch catches errors/fallbacks. Numeric integrity passes. | Hard-kill pending |
| Disk full at dump | Backup exception precedes mutation; focused test proves FAILED and no publication. Free storage and retry after review. | PASS |
| Concurrent close + deadline | Both serialize; deadline after close receives 409. Refresh and issue one action. | Integration race pending |
| Concurrent process + correction | Process locks game/round; correction lock equivalence not fully exercised. | Blocked |
| App/DB clock skew | Application decides deadline; skew tolerance is untested. Pause, repair NTP, extend equally. | Blocked |
| Session expires mid-submit | Auth rejects uncommitted request; atomic replace prevents partial state. Re-authenticate/resubmit if open. | Exercise pending |
| Frontend/backend partition | Unacknowledged request may fail while close proceeds. Use request ID/log and outage procedure. | Exercise pending |

No known scenario publishes a partial Phase-1 result. Five required isolated
infrastructure exercises still lack evidence, so V2-F is not an acceptance PASS.

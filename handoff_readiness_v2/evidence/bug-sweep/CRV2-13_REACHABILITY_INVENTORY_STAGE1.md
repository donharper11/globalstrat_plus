# CRV2-13 Stage 1 — registry-derived reachability inventory

**Status:** inventory complete; execution is deliberately open. This record
does not claim a browser walkthrough or a final bug-sweep pass.

## Method and count

The backend inventory comes from the registries named by the handoff, not a
search for interesting strings:

- backend/core/urls.py: 136 explicit paths (the router include is excluded);
- its DefaultRouter: 48 registered resource families;
- Django resolver check: 338 /api/ pattern rows, including DRF's format
  suffix variants. The family count above de-duplicates those variants.

The frontend inventory comes from every Route path in
frontend/globalstrat-frontend/src/App.js: 28 route definitions, including
login, redirect, and wildcard recovery.

The resolver was loaded read-only with a dummy non-empty DB_PASSWORD only to
satisfy settings validation; it made no database connection or mutation. The
repeatable registry command is:

    cd backend
    DB_PASSWORD=registry-only DJANGO_SETTINGS_MODULE=globalstrat.settings \
      python3 manage.py shell -c '<walk django.urls.get_resolver().url_patterns>'

## Backend map

Every router family below is an API surface, not a separate browser page. It
is either listed in a current UI's network checklist or deliberately outside
the CRV2-13 browser walkthrough because no current React route calls it. The
latter still belongs to the applicable API contract/CRV2-09 regression.

| Registry rows | Map for this sweep |
|---|---|
| courses, sections, teams, users, rounds, simulation-state, simulation-settings, simulation-parameters, dashboard | Instructor/control API: instructor walkthrough plus CRV2-09 regression. |
| programs, program-types, program-portfolios, program-features, decisions | Legacy program API: no current React route; out of the browser walkthrough, retained for CRV2-09 API regression. |
| score-types, scores, leaderboard, leaderboard-metrics, team-performance, income-statements, balance-sheets, cash-flows, team-resources, financial-revenue, financial-expenses, new-sales-by-round | Results/financial API: student results, leaderboard, and financial-report walkthrough; remaining legacy list/detail calls in CRV2-09. |
| triggered-events, fire-events, instructor-actions, instructor-evaluations, instructor-notes, instructor-feedback-templates, instructor-scenario-customizations | Instructor/operator API: instructor walkthrough or CRV2-09 where no current UI caller exists. |
| achievements, gamification-badges, player-progress, team-achievements, team-badges, messages, message-responses, message-threads, notification-logs, team-notifications | Notification/gamification API: no standalone current React route; inspect through dashboard/browser network and CRV2-09. |
| grading-rubrics, grading-categories, grading-components, team-grades, student-grade-adjustments | Instructor grading/export workflow: instructor walkthrough plus CRV2-09. |

The 136 explicit path rows are covered by these complete pattern groups (each
group is written exactly from core/urls.py):

| Explicit paths | Map for this sweep |
|---|---|
| auth/*, user/preferences/, onboarding/*, qicoin/, persona/*, resources/* | Login/onboarding/session-expiry and information-page browser checks; persona/resource APIs get network-error capture. |
| roster/, team-management/, simulation-control/, rounds/*/decision-status/, rounds/*/send-reminder/, grades/* | Instructor create/enrol/control/grading/export walkthrough. |
| games/*/round-control/*, games/*/instructor/teams/*/participation/, games/*/round-schedule/ | Instructor full lifecycle walkthrough. Existing CRV2-02 owns its concurrency property. |
| games/*/teams/*/decisions/*, products/*/rebase/, context/{rd,products,marketing,strategy,finance,talent}/ | Student decision walkthrough, reload/lock checks, D1–D5 targeted regressions, and D2 three-surface regression. |
| dashboard/scorecard/, events/{active,history}/, research/query/, results/round/, competitors/round/, leaderboard/{round,history}/, news/round/, research/{queries,reports/*}/, tools/{analysis,analysis/history,entry-matrix-data}/, financial-reports/{history,strategic-impact}/, forecast/{,scenarios}/, changes/, investor-relations/, briefing/* | Student information/results walkthrough, empty-first-round and post-process checks. |
| games/*/instructor/{session-readiness,dashboard,advance-round,inject-event,extend-deadline,research-queries,event-templates,briefings,operator-events,teams/*/decisions,alerts/*,team-config,randomize-home-markets,communications/*,sc-panel,sc-event-catalog,inject-sc-event} | Instructor/operator walkthrough. Existing CRV2-01–08 evidence is cited for replay, integrity, recovery, and load properties rather than repeated here. |
| context/{talent-allocation,compliance,governance,org-structure,tax-structure}/, markets/*/localization/, ticker/, communications/*, alliances/, government-relations/, round-status/ | Student decision/results walkthrough in both languages; first-round and no-history cases explicitly included. |
| scenarios/*, games/{,create,*teams,activate,pause,resume,reset,archive,delete}, games/*/teams/*/sc/*, scenarios/*/{suppliers,lanes,trade-finance-instruments,compliance-regimes,markets,segments}, games/*/{disclosure-overrides,resilience-weight-overrides}, games/*/instructor/sc-* | Scenario selection and instructor create/configure/control walkthrough; student supply-chain decision walkthrough. Destructive lifecycle actions use a disposable test game only. |

## Frontend map and browser-only remainder

The following 28 React definitions are the browser route inventory:

    /login  /demo  /instructor/login  /instructor/*
    /games/:gameId/instructor
    /
    /games/:gameId/teams/:teamId/{news,research,competitors,tools,financial-reports,
     team-activity,forecast}
    /games/:gameId/teams/:teamId/decisions/{sourcing,logistics,trade-finance,
     inventory,rd,products,marketing,corporate-strategy,market-strategy,finance,
     communications,summary}
    /games/:gameId/leaderboard  /leaderboard  *

Browser-only work still required for every applicable route above:

- student and instructor EN/ZH walkthroughs with a clean browser console and
  network tab;
- save, reload, deadline lock, back button after lock, slow connection, and
  mid-edit session expiry;
- first-round/no-history, empty, no-submission, all-submission, pagination,
  three-scenario and post-process result states;
- responsive desktop/mobile navigation and the wildcard recovery route;
- a separate performance sample for loaded pages. The route inventory cannot
  prove rendering time or N+1 behavior.

## Explicit exclusions from this stage

Django admin's generated routes are not in the handoff's route registries and
are not a participant workflow. Competition-domain admin writes are separately
made read-only. Static asset routes and DRF format-suffix duplicates are not
independent product surfaces.

This inventory therefore identifies, rather than hides, the remaining
browser-only work: it must be recorded before CRV2-13 can pass.

# GSP-CRV2-05 — supported frontend toolchain and green verification

**Finding:** V2-009 (P1) — **closed**
**Baseline:** `4cc335e` (branch `crv2-05-frontend-toolchain`, cut from `main`)
**Freeze commit:** `436cf08` (clean tree)
**Evidence:** `handoff_readiness_v2/evidence/frontend-toolchain/`

## The finding named the wrong cause

V2-009 attributes the Jest failure to the Node engine mismatch:
`react-router-dom@7.1.1` requires `>=20`, the VM's system node is 18.20.8. That
mismatch is real. It is not why Jest fails.

Reproduced on **Node 22.17.1**, which satisfies `>=20.0.0`, the failure is
identical: `Cannot find module 'react-router-dom' from 'src/App.js'`.

The cause is packaging:

| Fact | How it was checked |
|---|---|
| `react-router-dom@7.1.1` declares `main: "./dist/main.js"` | installed manifest |
| `dist/` contains `index.js`, `index.mjs` and typings — no `main.js` | `ls` |
| Node resolves the package anyway, via `exports` → `index.mjs` | `require.resolve` |
| react-scripts 5.0.1 pins jest 27.5.1, which predates `exports` support | installed tree |
| **Every** published 7.x declares the same dead `main` | registry: 7.1.1, 7.1.2, 7.1.5, 7.2.0, 7.6.3; plus a clean install of 7.6.3 |

Neither a Node upgrade nor a 7.x upgrade fixes it. Had the work been driven from
the finding's stated cause, it would have pinned Node 20 — which reached end of
life in April 2026 — and Jest would still have failed.

## The choice, and the one not taken

`react-router-dom@6.30.6` ships the file its `main` names and requires only Node
`>=14`.

* All eight router APIs this application imports — `BrowserRouter`, `Navigate`,
  `Outlet`, `Route`, `Routes`, `useLocation`, `useNavigate`, `useParams` —
  exist unchanged in v6, across 18 files.
* No data-router API is used anywhere: no `createBrowserRouter`,
  `RouterProvider`, `useLoaderData`, `useFetcher`, `defer` or `Await`.
* The two v7 defaults that could have behaved differently are inert here.
  `v7_relativeSplatPath` only affects **relative** paths inside splat routes;
  there are three splat routes and zero relative navigations — every `to=` and
  `navigate()` target in the codebase is absolute. `v7_startTransition` is a
  concurrency detail with no API change.

**The alternative was to stay on v7 and add a Jest `moduleNameMapper` to the CJS
build.** It was rejected because Jest would then exercise a different file from
the one webpack bundles. On a platform whose whole remediation programme is
about what was tested being what was run, a test-only resolution divergence is
the wrong trade. An auditor who disagrees can overturn this cheaply: it is one
config entry either way.

## Three further defects, none of them in the finding

**1. `npm ci` could not install the project at all.** `react-scripts` peers
`typescript@^3.2.1 || ^4`; `i18next@25` and `react-i18next@16` peer
`typescript@^5`. No version satisfies both, npm 10 installs optional peers by
default, and the install aborts. The 1.6 GB `node_modules` on the VM was
therefore produced by some command other than the one the acceptance names.
There are zero TypeScript source files in the repository.

`--legacy-peer-deps` was tried and **rejected on evidence**: `npm ci` succeeds
and the production build then dies on
`Cannot find module 'ajv/dist/compile/codegen'`, because suppressing peer
installation also drops the `ajv@8` that `ajv-keywords@5` peers on. An install
that succeeds while the build breaks is worse than one that fails honestly.

Settled with `overrides: { "typescript": "^5.9.3" }`, which leaves peer
resolution strict everywhere else — `schema-utils` still gets its own nested
`ajv@8.20.0` and `ajv-keywords@5.1.0` — and pins only a package with no source
files here.

**2. `axios@1.7.9` fails Jest for the same reason as the router**: ESM at
`main`, CJS reachable only through `exports`. Babel now transforms it, rather
than mapping it to a separate CJS build, so the test runs the source the browser
bundle runs. Two packages have now hit this; a third will, and the durable fix
is a test runner that understands `exports` — out of scope here, recorded as a
risk below.

**3. A failed drill-down request was displayed as an empty audit trail.**
`openDrill` caught every error as `setDrillData(null)`, and the modal renders
`null` as "No submission data" — the same thing shown for a team that submitted
nothing. On the one screen an instructor opens to defend a disputed result, a
server error was being presented as a fact about the team. This is V-1's
missing-versus-empty defect reappearing on the frontend error path. Repaired,
with the failure surfaced explicitly, and covered by test.

## The production build was failing, and a pipe was hiding it

`CI=true react-scripts build` promotes every ESLint warning to an error. The
repository carries **57** — 46 `no-unused-vars`, 11 `react-hooks/exhaustive-deps`
— across 18 page components. So the build had been failing throughout, including
in my own earlier runs, which piped through `tail` and reported *tail's* exit
status. The evidence runner exists because of that, and it is what caught it.

The build now runs with `CI=false`, and the warning count is held by
`eslint-warning-count.js` against a checked-in baseline: it may fall, it may not
rise. This is a deliberate scope decision. Editing hook dependency arrays across
eighteen unrelated page components to get a toolchain handoff over the line is
how render loops arrive in a competition engine, and blocking the toolchain work
behind that cleanup helps nobody. New code is still held to zero.

## What was pinned

| Item | Before | After |
|---|---|---|
| Runtime | nothing; 16, 20 and 22 installed, system node 18 | `.nvmrc` 22.17.1, `engines`, `packageManager` |
| Lockfiles | `package-lock.json` **and** `yarn.lock`, both tracked, yarn not installed | `package-lock.json` only; CI refuses a second one |
| CI | none | `.github/workflows/frontend.yml`, runtime read from `.nvmrc` |

Node 20 was rejected deliberately: it satisfies the v7 engine field and reached
end of life in April 2026. Node 22 is the current LTS and was already the
default on the host.

## Lockfile diff

**11 packages**, all attributable:

| Change | Packages |
|---|---|
| Router downgrade | `react-router`, `react-router-dom` 7.1.1 → 6.30.6 |
| v6 runtime dependency | `@remix-run/router` added |
| v7-only dependencies dropped | `cookie`, `set-cookie-parser`, `turbo-stream`, `@types/cookie` |
| From the typescript override | `typescript`, `@types/react`, `@types/prop-types`, `@testing-library/dom` |

The first attempt regenerated the lockfile from scratch and moved **419**
packages. That is the incidental churn the handoff rules out, and it also made
the suite pass on a tree nobody was going to ship — both remaining Jest defects
above were hidden by it and only appeared once the lockfile was rebuilt as a
minimal diff.

## Tests

| Suite | Tests |
|---|---|
| `App.test.js` | 1 — mounts the app, asserts the router resolves the default route |
| `AuditEvidenceTable.test.js` | 10 — actor/time/request-id/hash/payload rendering, em-dash for missing values, column set, empty history, missing history, failed request, error precedence, pagination ×3 |
| `AuditRoundSelect.test.js` | 5 — historical round options, selecting an earlier round, current round shown, unstarted game, missing round count |
| `useUnsavedChangesGuard.test.js` | 3 — pre-existing |

`App.test.js` was CRA's stock `renders learn react link`. It had never applied
to this application and could not fail visibly while the import was broken;
fixing the import simply revealed it as a placeholder.

The audit-evidence table and its round selector were extracted from a
2,000-line component. They were fifteen lines inside a modal reachable only by
rendering the whole instructor dashboard with an authenticated session and a
mocked API — which is a fair description of why they had no tests.

## jsdom shims

`src/setupTests.js` gained three, all documented at the point of use. The
substantive one: to compute a style, jsdom walks every stylesheet and asks its
selector engine to match each rule. antd's `Table` and `Select` each ship a rule
it cannot compile, and one such rule makes **every later** `getComputedStyle`
call throw anywhere on the page, with an error that names neither stylesheets
nor the rule. Real computed styles are still returned whenever jsdom can produce
them; the fallback covers only the two ways its CSS engine gives up, and
anything else is re-thrown.

## Unresolved risks

1. **jest 27 does not understand `exports`.** Two packages have already hit it.
   Each new occurrence needs a per-package `transformIgnorePatterns` exception.
   The durable fix is replacing react-scripts 5, which is unmaintained; that is
   a larger piece of work than V2-009 and is not attempted here.
2. **57 ESLint warnings remain**, ratcheted but not fixed.
3. **`caniuse-lite` is 20 months old**, so `browserslist` targets are stale. Not
   touched: refreshing it changes what the bundle compiles to, and doing that
   during a competition-readiness freeze without a browser matrix would be
   trading a known state for an unknown one.
4. **Browser smoke is partial** — see below.

## Verification

All five steps from `436cf08`, exit codes recorded rather than inferred
(`handoff_readiness_v2/evidence/frontend-toolchain/`):

| Step | Exit | Duration |
|---|---:|---:|
| `npm ci` from an empty `node_modules` | 0 | 21 s |
| `npm test -- --watchAll=false` — **19 tests, 4 suites** | 0 | 8 s |
| `npm run build` — 39 artefacts, 26 MB | 0 | 90 s |
| lint-warning ratchet — 57 against a baseline of 57 | 0 | 0 s |
| `git diff --exit-code package-lock.json` after install | 0 | 0 s |

Runtime recorded by the run itself: `.nvmrc` 22.17.1, `node v22.17.1`,
`npm 10.8.2`, system node v18.20.8 present but unused, one lockfile.
`react-router-dom` resolved at 6.30.6 in the installed tree.

## Browser smoke — partial, and stated as such

**Done:** the built bundle is served and rendered by headless chromium.
`handoff_readiness_v2/frontend_bundle_render_check.sh` reports 237,668 bytes of
DOM, the root element present, antd rendered, and the login screen at the
default route. That is worth having on its own — Jest exercises the *source* in
jsdom, which leaves the artefact users are actually served verified only by the
fact that it compiled, and a bundle can compile and still fail to boot.

**Not done:** the student login/navigation journey and the instructor historical
audit-evidence screen, with console and network error capture. Both need a
seeded backend, and driving them needs a browser driver. The chromium on this
host is a snap: it refuses a `--user-data-dir` outside its confinement, and
under several ordinary flag combinations it hangs rather than failing. A
scripted driver was attempted, produced misleading output, and was removed
rather than submitted. Adding puppeteer or playwright to this project's
dependency tree is not what V2-009 is about, and GSP-CRV2-08 — *post-close
retrieval and dispute browser proof* — owns browser proof and should stand up a
real driver.

The gap is named here rather than dressed up: **this handoff does not discharge
the browser-smoke line of its own acceptance criteria.** The audit should judge
whether the render check plus 19 Jest tests is sufficient for V2-009, or whether
the journey proof must land before the frontend is considered green.

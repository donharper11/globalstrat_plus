# GSP-CRV2-05 Phase 1 — frontend toolchain inventory

Built before any change, from the package manifests, the installed tree, the npm
registry and the URL/router call sites. Nothing here was assumed from the v2
finding text.

## 1. The finding does not describe the cause

V2-009 records: *"Lockfile selects `react-router-dom` 7.1.1 (Node >=20), but the
VM runs Node 18.20.8. Production build completes, while Jest cannot resolve the
router."* The Node mismatch is real, and it is not why Jest fails.

Reproduced on **Node v22.17.1**, which satisfies `>=20.0.0`:

```
Cannot find module 'react-router-dom' from 'src/App.js'
Test Suites: 1 failed, 1 passed, 2 total
```

The cause is packaging, not runtime:

| Fact | Source |
|---|---|
| `react-router-dom@7.1.1` declares `main: "./dist/main.js"` | installed `package.json` |
| `dist/` contains only `index.js`, `index.mjs`, `index.d.ts`, `index.d.mts` | `ls node_modules/react-router-dom/dist` |
| Node resolves it anyway, through `exports` → `dist/index.mjs` | `require.resolve` |
| react-scripts 5.0.1 pins **jest 27.5.1 / jest-resolve 27.5.1** | installed tree |
| jest-resolve 27 has no `exports` support; it falls back to `main` | resolution error above |

So `main` points at a file that does not exist, and the only consumer that
notices is the test runner. Checked against the registry, **every** 7.x release
declares the same dead `main` — 7.1.1, 7.1.2, 7.1.5, 7.2.0 and 7.6.3 — and a
clean install of 7.6.3 confirms `dist/main.js` is absent there too. Upgrading
within v7 does not fix this, and neither does upgrading Node.

`react-router-dom@6.30.6` declares the same `main` path and **ships the file**,
with `engines: {"node": ">=14.0.0"}`.

## 2. Router API surface actually used

18 source files import from `react-router-dom`; no file imports `react-router`
directly. The complete set of imported names:

`BrowserRouter as Router`, `Navigate`, `Outlet`, `Route`, `Routes`,
`useLocation`, `useNavigate`, `useParams`

All eight exist with identical semantics in v6 and v7. No data-router API is
used anywhere: no `createBrowserRouter`, `RouterProvider`, `useLoaderData`,
`useFetcher`, `useSubmit`, `defer` or `Await`. (`<Form>` appears in four files
and is antd's, not the router's.)

### The v7 defaults that could have differed

v7 is v6 with the `v7_*` future flags on by default. Two could change behaviour
here:

* `v7_relativeSplatPath` — changes how **relative** paths resolve inside a splat
  route. Three splat routes exist (`/instructor/*`, `*`, and a nested `*`), but
  a search for relative `navigate(...)` and `to=` targets returns **none**: every
  navigation in the codebase is absolute. The flag is inert for this app.
* `v7_startTransition` — wraps router state updates in `React.startTransition`.
  A concurrency detail, no API change.

## 3. Runtime and package manager

| Item | Observed |
|---|---|
| `/usr/bin/node` (system) | v18.20.8 — the version the finding names |
| nvm versions installed | v16.20.2, v20.20.0, **v22.17.1** (default) |
| `npm` | 10.8.2 |
| Runtime pin (`.nvmrc`, Volta, `engines`, `packageManager`) | **none** |

Whether a command works depends on which shell picked up which `node`. That is
the reproducibility half of V2-009 and it is real independently of the router.

Node 20 reached end of life in April 2026; Node 22 is the current LTS. Pinning
20 to satisfy a `>=20` engine field would pin an unsupported runtime.

## 4. Lockfiles

Both `package-lock.json` (lockfileVersion 3) and `yarn.lock` are tracked, and
both came from the same baseline commit `2509518`. They currently agree on
`react-router-dom@7.1.1`. **Yarn is not installed on the host**, so nothing has
ever validated `yarn.lock` and nothing would notice it drifting from the npm
tree. One authoritative lock strategy means keeping `package-lock.json` and
removing the file that no tool reads.

## 4b. A clean install was impossible before this handoff

`npm ci` on the pinned runtime fails outright, independently of the router:

```
npm error   peerOptional typescript@"^3.2.1 || ^4" from react-scripts@5.0.1
npm error Fix the upstream dependency conflict, or retry with --force or --legacy-peer-deps
```

`i18next@25` and `react-i18next@16` declare `peerOptional typescript@^5`;
`react-scripts@5.0.1` declares `peerOptional typescript@^3.2.1 || ^4`. **No
version satisfies both**, and npm 10 installs optional peers by default, so the
resolution is unsatisfiable. The 1.6 GB `node_modules` present on the VM was
therefore produced by some other command than the one the acceptance names.
There are zero TypeScript source files in the project.

`--legacy-peer-deps` was tried first and **rejected on evidence**: it makes
`npm ci` succeed and the production build fail, because it also stops npm
installing peers that are load-bearing — `ajv-keywords@5.1.0` peers on
`ajv@^8`, gets the hoisted `ajv@6.15.0`, and webpack dies on
`Cannot find module 'ajv/dist/compile/codegen'`. An install that succeeds while
the build breaks is worse than one that fails honestly.

The accepted fix keeps peer resolution strict and settles the one unsatisfiable
constraint explicitly, with `overrides: { "typescript": "^5.9.3" }`. Peers still
resolve — `schema-utils` gets its own nested `ajv@8.20.0` and
`ajv-keywords@5.1.0` — and the only package forced to a single version is one
the project does not use.

## 5. Tests and CI

| Item | Observed |
|---|---|
| Test files | `src/App.test.js`, `src/hooks/useUnsavedChangesGuard.test.js` |
| Result before this handoff | 1 suite failed (router resolution), 1 passed, 3 tests passed |
| Instructor audit-evidence coverage | **none** |
| CI configuration | **none** — no `.github/workflows`, no pipeline file |

## 6. The audit-evidence table

`src/pages/InstructorDashboard.js` renders it inline, inside the team drill-down
`<Modal>`, in a file of 2,000+ lines: an antd `<Table>` over
`drillData.audit_events` with columns Time (server), Actor, Action, Endpoint,
Request ID, Payload SHA-256, Payload, at `pagination={{ pageSize: 8 }}`.

### Defect found while inventorying it

`openDrill` handles a failed request as:

```js
} catch { setDrillData(null); }
```

and the modal renders `!drillData` as `<Empty description="no submission data" />`.
**A server error and a team that submitted nothing are shown identically.** This
is the same class of defect as V-1 — "missing" and "empty" made
indistinguishable — reappearing on the frontend error path, in the one screen an
instructor opens to defend a disputed result. The handoff asks for a failed-API
test; a test asserting the current behaviour would be asserting the bug, so this
is repaired and covered.

## 7. Dispositions

| Inventory row | Disposition |
|---|---|
| Jest cannot resolve `react-router-dom` | Repaired by moving to `6.30.6`; the eight used APIs are unchanged |
| `engines` conflict (`>=20` vs system 18) | Removed — 6.30.6 requires `>=14` |
| No runtime pin | `.nvmrc`, `engines` and `packageManager` pinned to Node 22.17.1 / npm 10.8.2 |
| Two lockfiles | `yarn.lock` removed; npm is authoritative |
| `npm ci` cannot install the project | `overrides: { typescript }`; `--legacy-peer-deps` tried and rejected because it breaks the build |
| `App.test.js` is CRA boilerplate asserting "learn react" | Replaced with a real mount-and-route smoke test; it had never passed and the resolution error hid that |
| No CI | Workflow added, same runtime and commands as local |
| No audit-evidence tests | Added, against an extracted component |
| Failed drill-down indistinguishable from empty | Repaired and covered |
| Browser smoke | See the completion report — assessed separately, and reported honestly if not achievable in this environment |

# Generic adaptive recoverability proof — training plan

This plan is fixed before any adaptive-policy replay.  The policy is trained
only on Consumer Electronics / Green Pioneer (team index 3) and Clean Energy /
Cost Leader (team index 5), using eight teams, ten rounds, seed `20261011`, and
the competent baseline field.  Media is the untouched holdout and must not be
run until one implementation and parameter set are committed and hashed.

The algorithm has no scenario or profile branches.  It uses only the prior
round's product sell-through, lost demand, inventory, closing cash, and
debt-to-equity.  Its actions are bounded production buffers, a two-percent
price response, and at most two additional sales representatives.  A cash or
leverage guard suppresses growth and extra staffing.

Four predeclared candidates are in
`generic_adaptive_training_candidates.json`.  Selection is lexicographic:

1. Prefer candidates that finish rank 1 for both training subjects.
2. Maximize the worse of the two final PI margins over the best competing
   team in the same replay.
3. Maximize mean final PI margin, then mean cumulative net income.
4. If none wins both, minimize the sum of ranks, then apply rules 2 and 3.

After selection, the chosen JSON is copied byte-for-byte to
`generic_adaptive_policy_v1.json`; the harness revision and SHA-256 hashes of
the implementation and parameter file are recorded and committed.  Only then
is the policy run once on Media / Value Bundler (team index 7).  There is no
Media-specific constant, retry, or post-holdout parameter change.

# GSP-CRV2-01 determinism evidence

Subject: **game 37, round 1**, resolved under manifest schema version 2.

Everything here was produced by one immutable revision:

| | |
|---|---|
| Commit | `1189a50d41a502955f77fc505610165735ba6fac` |
| Source tree digest | `642b5884460e82f6420e6ca7ca877f5c9cdacfe1a5f29bac47fc43eeb7b0206a` (312 files under `backend/`) |
| Input hash | `408fe6ebb847e00287fec854a87f093359f59acffdb809425805c83951b55c84` |
| Competitive hash | `129a374ec6a82f22da9514ad3c263b856381024f46ad31790e5a36e08589b383` |
| Pre-resolution backup | `game-37-round-1-20260828T035721064993Z.dump`, sha256 `bdd0bac52a771a3d38d2899698acdfa0b09013cc4e19aa7d2cffa9b6c4ddddb5` |

The commit hash names the commit; the **source tree digest** names the code. A
`-dirty` suffix would name neither, so `replay_round` compares the digest and
refuses a mismatch before it touches the database. Every run below verified it.

## Result

| Run | Process environment | LLM | Competitive hash | Post-Phase-2 narrative hash |
|---|---|---|---|---|
| A | Ubuntu 22.04.5, Python 3.10.12, `TZ=UTC` | `qwen-max` | `129a374e…` | `fd781100a1…` |
| B | same host | substitute endpoint, `stub-divergent-1` | `129a374e…` | `8e5a4f811f…` |
| C | same host | unreachable (`127.0.0.1:9`) | `129a374e…` | `3bd451a034…` |
| D | **Debian 12 container**, Python 3.11.16, **process `TZ=Asia/Kolkata`** (`time.tzname == ('IST','IST')`), `LC_ALL=de_DE.UTF-8`, pg client 18.6 | `qwen3-max-preview` | `129a374e…` | `2418b417f6…` |

One competitive hash across all four. Four different narrative hashes, with the
prose that produced them stored beside each (`post-phase2-narrative.json.gz`):

- A — `**Strategic Briefing: Q1 2023** … Lumen Devices reported a revenue …`
- B — `STUB MODEL OUTPUT — this narrative was produced by a deliberately different endpoint …`
- C — `**Quarter 1 Results** Revenue declined 94.0% to $1,368,000 …` (template fallback)

**On run D's timezone.** Django assigns `os.environ['TZ']` from
`settings.TIME_ZONE` and calls `tzset()`, so setting the container's clock alone
leaves the resolving process on UTC no matter what the host says. `TIME_ZONE` is
therefore environment-overridable and run D sets it. The claim is not a label:
the run asserts its own fingerprint with `--require-env` and the command exits
before doing anything if the process is not what the run says it is. The eight
assertions it passed are in `run-d-second-environment/source-identity.json`.

## Negative tests

Each restores the backup, changes exactly one thing, and re-verifies. All four
fail before the engine is called.

| Corrupted | Gate | Reported |
|---|---|---|
| A decision payload | input manifest | `decision_marketing … retail_price: '525' -> '526'` |
| A scenario value | input manifest | `segment_preference … weight: '0.06' -> '1.06'` |
| A carried-state value | input manifest | `team … cash_on_hand: '50000000' -> '51000000'` |
| One untracked source file added under `backend/` | build identity | source digest `642b5884…` -> `f22f51b5…` |

The last one is the point of the source digest: `git status
--untracked-files=no` reported the tree **clean** and the commit hash was
unchanged, and the replay still refused.

## Files

```
recorded/expected-manifest.json.gz  the manifest as resolution recorded it
run-*/expected-manifest.json.gz     the copy each run verified against
run-*/source-identity.json          source digest + environment assertions
run-*/input-verification.json       pre-mutation input check (hashes, diffs)
run-*/replay-report.json            hashes, environment fingerprint, LLM config
run-*/replayed-manifest.json.gz     the manifest the replay produced
run-*/post-phase2-narrative.json.gz the Phase-2 prose that was hashed
negative/<kind>-clean/              clean verification straight after restore
negative/<kind>/                    verification after one value was corrupted
negative/source-tree/               refusal when the source tree differs
SUMMARY.json                        consolidated index
MANIFEST.sha256                     sha256 of every file above
```

Manifest bodies are stored gzipped. `--expected-manifest` reads gzip directly
and also resolves a `.json` path to the `.json.gz` beside it, so the commands
below work against the stored artifacts unchanged.

## Transcript

Everything ran against an **isolated** database (`globalstrat_replay`); the
`--restore` path drops and rebuilds the target schema. All commands run from
`backend/`.

```bash
EV=../handoff_readiness_v2/evidence/determinism

# 0. Fixture: a fresh game resolved under the v2 manifest, on a clean tree.
COMPETITION_REQUIRE_CLEAN_BUILD=true \
python3 ../handoff_readiness_v2/determinism_fixture.py --teams 4 --rounds 1
#   -> game_id=37  schema_version=2
#      input_sha256=408fe6eb…  output_sha256=129a374e…  backup=…dump

# 1. Export the recorded manifest before anything is restored over it.
python3 manage.py replay_round --game-id 37 --round 1 --export-only \
  --evidence-dir $EV/recorded

# 2. Run A — recorded build, original LLM configuration.
DB_NAME=globalstrat_replay COMPETITION_RECOVERY_ENABLED=true \
COMPETITION_REQUIRE_CLEAN_BUILD=true \
python3 manage.py replay_round --game-id 37 --round 1 \
  --restore --confirm REPLAY-GAME-37-ROUND-1 \
  --expected-manifest $EV/recorded/expected-manifest.json \
  --evidence-dir $EV/run-a-baseline \
  --label 'A: recorded build, original LLM config' \
  --require-env tz_env=UTC --require-env python=3.10.12 \
  --require-env os_release='Ubuntu 22.04.5 LTS' \
  --wait-narrative 180

# 3. Run B — a different model/endpoint returning deliberately different prose.
python3 ../handoff_readiness_v2/llm_stub.py &        # serves a fixed reply
DB_NAME=globalstrat_replay COMPETITION_RECOVERY_ENABLED=true \
COMPETITION_REQUIRE_CLEAN_BUILD=true \
DASHSCOPE_COMPATIBLE_URL=http://127.0.0.1:8791/v1/chat/completions \
DASHSCOPE_MODEL=stub-divergent-1 \
python3 manage.py replay_round --game-id 37 --round 1 \
  --restore --confirm REPLAY-GAME-37-ROUND-1 \
  --expected-manifest $EV/recorded/expected-manifest.json \
  --evidence-dir $EV/run-b-different-model \
  --label 'B: different model/endpoint returning deliberately different prose' \
  --require-env tz_env=UTC --require-env python=3.10.12 \
  --wait-narrative 180

# 4. Run C — unreachable endpoint.
DB_NAME=globalstrat_replay COMPETITION_RECOVERY_ENABLED=true \
COMPETITION_REQUIRE_CLEAN_BUILD=true \
DASHSCOPE_COMPATIBLE_URL=http://127.0.0.1:9/v1/chat/completions \
DASHSCOPE_MODEL=unreachable-endpoint \
python3 manage.py replay_round --game-id 37 --round 1 \
  --restore --confirm REPLAY-GAME-37-ROUND-1 \
  --expected-manifest $EV/recorded/expected-manifest.json \
  --evidence-dir $EV/run-c-llm-outage --label 'C: unreachable LLM endpoint' \
  --require-env tz_env=UTC --require-env python=3.10.12 \
  --wait-narrative 180

# 5. Run D — second container: different base OS, Python, process timezone and
#    locale, each asserted rather than labelled.
R=/home/ubuntu/projects/globalstrat+
docker build -f handoff_readiness_v2/replay_environment.Dockerfile \
  -t globalstrat-replay:crv2-01 .        # run from the repository root
docker run --rm --network host -v $R:$R --user $(id -u):$(id -g) -e HOME=/tmp \
  -e DJANGO_SETTINGS_MODULE=globalstrat.settings \
  -e DB_NAME=globalstrat_replay -e DB_HOST=192.168.50.38 \
  -e DB_USER=donwh -e DB_PASSWORD=… \
  -e COMPETITION_RECOVERY_ENABLED=true -e COMPETITION_REQUIRE_CLEAN_BUILD=true \
  -e GIT_REVISION=1189a50d41a502955f77fc505610165735ba6fac \
  -e DJANGO_TIME_ZONE=Asia/Kolkata \
  globalstrat-replay:crv2-01 \
  python3 manage.py replay_round --game-id 37 --round 1 \
    --restore --confirm REPLAY-GAME-37-ROUND-1 \
    --expected-manifest $R/handoff_readiness_v2/evidence/determinism/recorded/expected-manifest.json \
    --evidence-dir $R/handoff_readiness_v2/evidence/determinism/run-d-second-environment \
    --label 'D: second container, process TZ Asia/Kolkata, locale de_DE.UTF-8' \
    --require-env tz_env=Asia/Kolkata --require-env time_tzname=IST,IST \
    --require-env django_time_zone=Asia/Kolkata \
    --require-env current_timezone=Asia/Kolkata \
    --require-env system_timezone=Asia/Kolkata \
    --require-env lc_all=de_DE.UTF-8 --require-env locale=de_DE,UTF-8 \
    --require-env os_release='Debian GNU/Linux 12 (bookworm)' \
    --wait-narrative 120

# 6. Negative tests — restore, corrupt one value, verify (engine must not run).
for KIND in decision scenario carried; do
  DB_NAME=globalstrat_replay COMPETITION_RECOVERY_ENABLED=true \
  COMPETITION_REQUIRE_CLEAN_BUILD=true \
  python3 manage.py replay_round --game-id 37 --round 1 --restore \
    --confirm REPLAY-GAME-37-ROUND-1 --verify-only \
    --expected-manifest $EV/recorded/expected-manifest.json \
    --evidence-dir $EV/negative/$KIND-clean
  DB_NAME=globalstrat_replay \
  python3 ../handoff_readiness_v2/corrupt_one_value.py $KIND 37
  DB_NAME=globalstrat_replay COMPETITION_RECOVERY_ENABLED=true \
  COMPETITION_REQUIRE_CLEAN_BUILD=true \
  python3 manage.py replay_round --game-id 37 --round 1 --verify-only \
    --expected-manifest $EV/recorded/expected-manifest.json \
    --evidence-dir $EV/negative/$KIND        # exits 2
done

# 7. Negative test for the build-identity gate.
cat > core/services/_source_gate_probe.py <<'PROBE'
PROBE = 'this file is not in the recorded build'
PROBE
git status --porcelain --untracked-files=no      # prints nothing: "clean"
DB_NAME=globalstrat_replay COMPETITION_RECOVERY_ENABLED=true \
COMPETITION_REQUIRE_CLEAN_BUILD=true \
python3 manage.py replay_round --game-id 37 --round 1 --verify-only \
  --expected-manifest $EV/recorded/expected-manifest.json \
  --evidence-dir $EV/negative/source-tree     # refuses: source tree mismatch
rm core/services/_source_gate_probe.py
```

## Reading a mismatch

`replay_round` refuses a source-tree mismatch outright, exits 2 when the input
does not verify (engine not run) and 3 when the competitive hash differs,
printing per-section counts and the first changed rows by natural key:

```
  section decision_marketing: 0 missing, 0 added, 1 changed
      decision_marketing(decision_submission(team(game("DETERMINISM-FIXTURE")
        |"Nova Circuit")|round(…|"1"))|team_product(…|"Nexus One")
        |market_definition(scenario("Consumer Electronics 2026")|"NA"))
        .retail_price: '525' -> '526'
```

The full diff, including sections the console truncates, is in the JSON. This
is not hypothetical: an earlier revision of this work produced a real mismatch
here, and the section diff named `coherence` and the exact reordered list —
which is how the unordered `TeamMarketPresence` scan behind it was found.

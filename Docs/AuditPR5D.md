# Audit Report: PR1–PR5 (PR5D)

**Date:** $(date '+%Y-%m-%d %H:%M %Z')
**Auditor:** Codex (automated)
**Scope:** Roadmap PR1 through PR5 as defined in `Docs/roadmap.txt`

## Methodology
- Reviewed SPEC (`Docs/SPEC.md`) + roadmap to restate each PR’s target outcomes and merge gates.
- Traced the implementation across backend, alembic, adapters, tests, and docs looking for evidence of the required behavior.
- Verified unit/integration test coverage and looked for missing or brittle validation.
- Highlighted correctness gaps, architectural risks, and determinism issues relative to the spec.

## Completion Snapshot
| PR | Completion | Highlights | Key Risks |
| --- | --- | --- | --- |
| PR1 – Scaffolding & Contracts | **90%** | Contracts & settings implemented with CI + eval skeleton (`backend/app/models/*`, `.github/workflows/ci.yml`, `eval/runner.py`). | Locked-slot invariants not enforced; contracts already accept non-spec provenance sources. |
| PR2 – DB, Tenancy, Idempotency, Rate Limits | **80%** | Postgres models/migrations (`alembic/versions/001*.py`, backend models), tenancy helpers/tests, idempotency store, seeded data script. | Rate limiting/idempotency helpers never wired into API, and seed tests require a real Postgres connection, so CI will fail without infra. |
| PR3 – Tool Executor, Cancellation, Health, Metrics | **70%** | `ToolExecutor` has caching, retries, breaker, metrics, /healthz and metrics client tests. | Hard timeout + cancel plumbing missing outside executor; jitter/503 gates unverified; executor not integrated anywhere. |
| PR4 – Orchestrator, SSE, UI | **60%** | LangGraph nodes emit events, SSE endpoint + Streamlit vertical exist. | Background thread reuses FastAPI session after it closes, no LangGraph checkpoints, violations stored as dicts, SSE tests miss cross-org auth, blocking DB calls in async loop. |
| PR5 – Adapters, Feature Mapper, Provenance | **90%** | Real weather adapter w/ executor policies, fixture adapters w/ response digests, canonical feature mapper + tests, provenance helpers/tests. | Weather fallback still labels fixture data as `source="tool"`; provenance completeness not enforced by any adapter tests; selectors still see raw objects until PR6. |

---

## PR1 — Scaffolding, Contracts, Settings, Eval Skeleton (90%)

### Evidence of Completion
- Settings + `.env.example` implemented via `backend/app/config.py` and `.env.example`, and CI pipeline in `.github/workflows/ci.yml` runs ruff/black/mypy/pytest/schema export/eval as required.
- Pydantic contracts for intent/plan/itinerary/tool results live under `backend/app/models/*.py` (e.g., `common.py:14-142`, `intent.py:12-74`, `plan.py:13-118`, `tool_results.py:1-120`).
- Eval harness defined in `eval/runner.py` plus two stub scenarios in `eval/scenarios.yaml`.

### Gaps / Risks
- Spec invariant “locked_slots[].day_offset must fit within trip length” is not enforced—`IntentV1` only validates budget and airport count (`backend/app/models/intent.py:28-74`). An out-of-range locked slot will sail through and crash the planner later.
- Contracts already drift from the spec’s provenance enum by allowing arbitrary `source` values like "fake" (`backend/app/graph/nodes.py:56-101`), which erodes “contracts only across boundaries.”

### Recommendation
Add a validator on `Preferences.locked_slots` to clamp/validate offsets and reject invalid constraints up front; keep provenance sources spec-compliant even in stubs to avoid downstream surprises.

---

## PR2 — DB, Alembic, Tenancy, Idempotency, Rate Limits (80%)

### Evidence of Completion
- Alembic migration `001_initial_schema.py` creates org/user/refresh/destination/knowledge/embedding/agent_run/itinerary/idempotency tables with org-scoped constraints; `002_add_agent_run_event.py` adds the SSE log table.
- SQLAlchemy models live under `backend/app/db/models/*.py`, and tenancy helpers/tests exist (`backend/app/db/tenancy.py`, `tests/integration/test_tenancy.py`).
- Idempotency helpers + tests (`backend/app/idempotency/store.py`, `tests/integration/test_idempotency.py`).
- Redis token bucket implemented with tests (`backend/app/limits/rate_limit.py`, `tests/integration/test_rate_limit.py`).
- Seed script provided (`scripts/seed_fixtures.py`).

### Gaps / Risks
1. **Rate limiting not enforced anywhere.** A repo-wide search shows `check_rate_limit` is never invoked outside tests/docs, so API endpoints never emit 429s or retry-after headers (`rg check_rate_limit backend/app` only matches the helper). Merge gate “429 behavior deterministic” is therefore unmet.
2. **Idempotency unused.** Similar to rate limiting, none of the HTTP routes call `save_result/get_entry`, so duplicate POSTs will still double-execute.
3. **Seed tests require a live Postgres cluster.** `tests/integration/test_seed_fixtures.py` calls `seed_demo_data()`, which spins up a real engine via `get_session_factory()` (`scripts/seed_fixtures.py:22-80`). On a CI box without Postgres, those tests hang/fail, violating the “CI green” constraint.

### Recommendation
Introduce FastAPI dependencies/middleware that call `check_rate_limit` and the idempotency store in `/plan` before launching LangGraph; consider marking the seed tests with `@pytest.mark.integration` or injecting the test session factory to avoid networked DB requirements.

---

## PR3 — Tool Executor, Cancellation, /healthz, Metrics (70%)

### Evidence of Completion
- Resilient executor with caching, retries, breaker, and metrics lives in `backend/app/exec/executor.py` with comprehensive unit tests (`tests/unit/test_executor.py`).
- Metrics registry implemented in `backend/app/metrics/registry.py` with tests.
- `/healthz` checks Postgres + Redis (`backend/app/api/health.py`, `tests/unit/test_health.py`).

### Gaps / Risks
1. **Hard timeout missing.** Spec calls for 2 s soft + 4 s hard timeouts. `_execute_sync_with_timeout` and `_execute_async_with_timeout` only use `soft_timeout_s` (`backend/app/exec/executor.py:213-266`), so a stuck tool can run forever post-soft timeout.
2. **Cancellation isn’t plumbed.** While `CancelToken` exists, it’s never surfaced from the API/graph; only the executor tests instantiate it (`rg CancelToken` shows references limited to the executor and its tests). There’s no way to signal cancellation from `/plan/{run}/stream`.
3. **Breaker merge-gate tests incomplete.** No test asserts retry jitter stays within 200–500 ms bounds or that breaker headers propagate, even though the roadmap requires that.
4. **Executor unused.** LangGraph nodes still call fake logic; adapters don’t receive the executor, so none of the PR3 resilience actually protects runtime calls yet.

### Recommendation
Add a hard timeout watchdog (e.g., kill the threadpool future at 4 s), expose `CancelToken` through LangGraph state so callers can cancel runs, and port the executor into the adapter layer to prove the wiring before PR6.

---

## PR4 — Orchestrator Skeleton, SSE, Streamlit Vertical (60%)

### Evidence of Completion
- LangGraph nodes defined in `backend/app/graph/nodes.py` with stub planning + synthesis logic; SSE event log via `backend/app/db/agent_events.py` + `AgentRunEvent` model/migration.
- `/plan` POST and `/plan/{run_id}/stream` SSE implementation in `backend/app/api/plan.py` with throttling/heartbeat/resume, and a minimal Streamlit UI (removed from `frontend/plan_app.py`).

### Gaps / Risks
1. **Thread-unsafe session usage.** `start_run` shares the request-scoped SQLAlchemy session with a background thread (`backend/app/graph/runner.py:192-264`). FastAPI closes that session as soon as `create_plan` returns (`backend/app/api/plan.py:32-69`), so `_execute_graph` operates on a closed session and will throw `ResourceClosedError` under load.
2. **No LangGraph checkpoints.** `_execute_graph` compiles a graph but then manually iterates over a hard-coded `node_sequence` (`backend/app/graph/runner.py:90-146`). There’s no checkpoint/restore or typed edges, so the merge gate “nodes with checkpoints” isn’t met.
3. **Violations bypass the contract.** `verifier_node` appends raw dicts with `# type: ignore` to `state.violations` (`backend/app/graph/nodes.py:151-175`), violating the “contracts only across boundaries” rule.
4. **SSE coverage gaps.** Tests only prove that auth headers are required (`tests/unit/test_plan_api.py:12-68`); there’s no test ensuring cross-org run IDs return 403 as mandated in the roadmap.
5. **Blocking DB queries in async loop.** `stream_plan` calls `list_events_since` synchronously inside the async generator (`backend/app/api/plan.py:130-199`), which can stall the event loop when Postgres stalls. Consider using async sessions or `run_in_executor`.

### Recommendation
Refactor `start_run` to enqueue work into a background task that uses its own session (or pushes the intent onto a queue) and use LangGraph’s checkpointing primitives rather than manual loops. Expand SSE tests to cover cross-org protection and resume behavior.

---

## PR5 — Adapters, Canonical Feature Mapper, Provenance (90%)

### Evidence of Completion
- Real weather adapter with executor integration and fixture fallback (`backend/app/adapters/weather.py`) plus fixtures for flights/lodging/events/transit/fx with provenance digests (`backend/app/adapters/*.py`).
- Canonical feature mapper + tests (`backend/app/adapters/feature_mapper.py`, `tests/unit/test_feature_mapper.py`).
- Provenance helpers/tests (`backend/app/models/common.py:72-143`, `tests/unit/test_provenance.py`).

### Gaps / Risks
1. **Fixture fallback mislabeled.** When weather falls back to fixture data it still records `source="tool"` with a `fixture://` URL (`backend/app/adapters/weather.py:98-137`), so provenance consumers can’t distinguish real vs. fixture responses.
2. **Missing enforcement that adapters publish provenance.** There’s no test that fails when provenance is omitted/blank per the merge gate “missing provenance fails”—current tests only cover the helper, not enforcement at adapter outputs.
3. **Feature mapper isn’t yet enforced upstream.** PR5’s “no selector touching raw tool fields” goal is only partially satisfied; there’s no automated check preventing future code from bypassing `ChoiceFeatures`.

### Recommendation
Tag fallback provenance as `source="fixture"`, add adapter-level tests that assert `response_digest`/`fetched_at` presence, and gate selector inputs on `ChoiceFeatures` once PR6 wiring begins.


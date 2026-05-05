# Technical Concerns

_Last updated: 2026-05-05_

---

## High Priority

### 1. View projection is hardcoded — DB-backed projection not implemented

**Issue:** `src/scenario_db/view/service.py` contains `project_level0()`, `project_level1()`, and `project_level2()`. All three are stubs. When `db` is `None` the viewer falls back to a hardcoded sample (`build_sample_level0()`). When `db` is provided, Level 0 raises `NotImplementedError`; Levels 1 and 2 always raise `NotImplementedError`.

**Impact:** The FastAPI `/view` endpoint returns HTTP 501 for any DB-backed call. The Streamlit dashboard permanently serves the hardcoded "Camera FHD30" sample regardless of what scenario/variant is requested. No real scenario data is ever visualised.

**Files:**
- `src/scenario_db/view/service.py` — lines 233–249 (all three `project_*` functions)
- `src/scenario_db/api/routers/view.py` — line 42 (`except NotImplementedError`)
- `dashboard/pages/1_Pipeline_Viewer.py` — line 68–70 (`_load_view()` always calls `build_sample_level0`)

**Fix approach:** Implement `build_canonical_graph()` as a DB query that assembles a `ViewResponse` from ORM rows; wire into `project_level0()` when `db is not None`. This is the designated next milestone per `docs/implementation-roadmap-etl-resolver-api-viewer.md §4`.

---

### 2. No ReviewGateEngine — gate execution is not unified

**Issue:** Gate rule evaluation, issue matching, and waiver applicability exist as separate utilities (`matcher/runner.py`, `db/sql_matcher.py`, `api/cache.py`) but there is no single `ReviewGateEngine` service that accepts a `(scenario_id, variant_id, context)` tuple and returns a structured gate result.

**Impact:** Review gate checks cannot be triggered via API. Persisted runtime gate results do not exist. The decision layer is read-only via CRUD — there is no execution path.

**Files:**
- `src/scenario_db/matcher/runner.py`
- `src/scenario_db/db/sql_matcher.py`
- `src/scenario_db/api/cache.py` — `match_issues_for_variant()` is the closest to a service, but it is a standalone helper with no gate rule integration

**Fix approach:** Create `src/scenario_db/gate/engine.py` implementing `ReviewGateEngine.run(scenario_id, variant_id, db)` → structured result. Expose as a POST endpoint in a new `gate` router.

---

### 3. No canonical graph builder — ETL loads data but nothing assembles a resolved graph

**Issue:** ETL can load YAML into DB tables. However, nothing converts those rows into a resolved scenario graph object (the intermediate form that the viewer, gate engine, and resolver all need). `build_canonical_graph()` is referenced in the docstring of `service.py` line 3 but does not exist anywhere in the codebase.

**Impact:** Every consumer (viewer, gate, sim engine integration) must independently re-implement DB → graph assembly logic. Currently they all fall back to hardcoded sample data instead.

**Files:**
- `src/scenario_db/view/service.py` — docstring mentions `build_canonical_graph()` which is absent
- `src/scenario_db/etl/loader.py` — loads rows but produces no graph

**Fix approach:** Implement `src/scenario_db/view/graph_builder.py` with `build_canonical_graph(scenario_id, variant_id, session) -> CanonicalGraph`. Canonical graph must include resolved nodes, edges, matched issues, and evidence links.

---

## Technical Debt

### 4. `sys.path` manipulation in every dashboard entry point

**Issue:** Both `dashboard/Home.py` and `dashboard/pages/1_Pipeline_Viewer.py` manually insert `src/`, the repo root, and `dashboard/` into `sys.path` at import time. This is fragile and duplicated.

**Files:**
- `dashboard/Home.py` — lines 11–17
- `dashboard/pages/1_Pipeline_Viewer.py` — lines 10–16

**Fix approach:** Configure `pythonpath` in `pyproject.toml` under `[tool.pytest.ini_options]` and add a `dashboard/__main__.py` or `pth` file so Streamlit picks up the package paths automatically.

---

### 5. `RuleCache` has no invalidation trigger from write operations

**Issue:** `src/scenario_db/api/cache.py` documents that `@lru_cache(maxsize=512)` should be added to `match_issues_for_variant()` (TODO at line 91), and provides `invalidate_issues()` / `invalidate_gate_rules()` methods. However, no router currently calls these invalidation methods after any write. The cache can silently serve stale issue/gate-rule data after mutations.

**Files:**
- `src/scenario_db/api/cache.py` — line 91 (`# TODO Week 4`)
- `src/scenario_db/api/routers/decision.py` — no invalidation calls

**Fix approach:** Call `request.app.state.rule_cache.invalidate_issues(db)` in every POST/PUT/DELETE handler that modifies `Issue` or `GateRule` rows. Add the `@lru_cache` only after the invalidation path is confirmed correct.

---

### 6. SQL hybrid matcher silently skips `sw_feature`, `sw_component`, and `scope` conditions

**Issue:** `src/scenario_db/db/jsonb_ops.py` `match_condition_to_sql()` returns `None` for `sw_feature.*`, `sw_component.*`, and `scope.*` conditions (lines 160, 204). These fall through to a Python post-filter. The SQL pre-filter therefore provides only partial pre-screening, which means the "SQL-only" path in `sql_matcher.py` may emit false negatives if Python post-filter is not applied by the caller.

**Files:**
- `src/scenario_db/db/jsonb_ops.py` — lines 155–205
- `src/scenario_db/db/sql_matcher.py`

**Fix approach:** Document the two-phase contract explicitly. Add an assertion in `find_matching_issues_sql_hybrid()` that the Python post-filter is always applied after the SQL pre-filter, not optionally. Consider adding a counter in `BulkMatchReport` for "conditions skipped by SQL pre-filter".

---

### 7. Module name `elk_graph_builder.py` is misleading — ELK is not used

**Issue:** `dashboard/components/elk_graph_builder.py` exports `build_view_layout()` and a backward-compat alias `build_elk_graph()`. The module comment (line 3–4) explicitly states "ELK is NOT used here". The file and alias names imply ELK layout engine usage, which confuses future readers.

**Files:**
- `dashboard/components/elk_graph_builder.py`
- `dashboard/components/elk_viewer.py`

**Fix approach:** Rename `elk_graph_builder.py` → `view_layout_builder.py` and update all import sites. ELK.js is reserved for Level 1 compound layouts (per the design doc) and should only be introduced when Level 1 is implemented.

---

### 8. `viewer_implementation_prompts_v3.md` is an untracked working document at repo root

**Issue:** `viewer_implementation_prompts_v3.md` exists at the repo root as an untracked file (git status). It appears to be a prompt/design scratchpad that does not belong in version-controlled state.

**Files:**
- `viewer_implementation_prompts_v3.md` (untracked)

**Fix approach:** Either commit to `docs/` with a proper name or add to `.gitignore`.

---

## Known Issues / TODOs

### 9. Alembic has only one migration — no schema for resolver results or gate executions

**Issue:** `alembic/versions/0001_initial_schema.py` is the only migration. There is no table for persisted resolver output, runtime gate execution results, or scenario instances. These are required by the roadmap (Phase C) but adding them requires a new Alembic revision.

**Files:**
- `alembic/versions/0001_initial_schema.py`

**Fix approach:** Create `0002_resolver_gate_tables.py` migration when `ReviewGateEngine` is implemented.

---

### 10. Dashboard Level 1 and Level 2 view controls are non-functional placeholders

**Issue:** `dashboard/pages/1_Pipeline_Viewer.py` (lines 110–113) renders a radio group with "1 — IP DAG (Phase C)" and "2 — Drill-Down (Phase C)" options, but selecting them has no effect. The radio input is not wired to any state or rendering path.

**Files:**
- `dashboard/pages/1_Pipeline_Viewer.py` — lines 109–114

**Fix approach:** Either hide the radio until Level 1 is implemented, or wire a `st.session_state` variable that shows a "not implemented" banner when selected.

---

### 11. Evidence Dashboard and Issue Explorer home cards are disabled buttons

**Issue:** `dashboard/Home.py` renders "Evidence Dashboard" and "Issue Explorer" cards with `st.button(..., disabled=True)` and `badge-phase` badges. These features are planned but not started.

**Files:**
- `dashboard/Home.py` — lines 130, 144

---

### 12. `scope` matching always returns `True` in the Python runner

**Issue:** In `src/scenario_db/matcher/runner.py` line 39–40, any rule with a `scope` key and no `op` key is unconditionally returned as `True` (comment: "currently pass-through, Matcher v2"). This means scope-scoped rules are never evaluated and always match.

**Files:**
- `src/scenario_db/matcher/runner.py` — lines 38–41

**Fix approach:** Implement scope evaluation against `execution_context` in `MatcherContext`. Document scope semantics until then. Do not silently return `True`.

---

## Risk Areas

### 13. SimEngine integration is planned but not started — large scope gap

**Issue:** `docs/simulation-engine-integration.md` describes porting the SimEngine (`E:\10_Codes\23_MMIP_Scenario_simulation2`) BW/Power/Performance calculation engine into a `sim/` package within this project. No `sim/` package exists. This integration spans SimPy discrete-event simulation, DVFS resolution, and DMA BW modelling — a substantial separate codebase not yet connected.

**Impact:** `SimulationEvidence` in the DB schema has fields for KPIs (bandwidth, power, latency), but all values are currently manually authored in YAML fixtures. Automated simulation-backed evidence is unavailable.

**Files:**
- `docs/simulation-engine-integration.md`
- `src/scenario_db/db/models/evidence.py` — `SimulationEvidence` table

---

### 14. Node click → inspector panel is not connected through the SVG component

**Issue:** The SVG viewer rendered in `elk_viewer.py` handles `click` events inside inline JavaScript and shows a tooltip. However, the click event does not communicate the selected node ID back to Streamlit's Python state. The `render_level0()` function accepts a `selected_node` parameter (line 524) but the caller in `1_Pipeline_Viewer.py` never passes it and there is no bidirectional message channel (no `st.components.v1.declare_component` custom component, only `components.html`).

**Impact:** The inspector panel (`render_inspector`) always shows the static scenario summary and risks — it cannot display per-node details on click.

**Files:**
- `dashboard/components/elk_viewer.py` — `render_level0()` signature line 523, `selected_node` unused
- `dashboard/pages/1_Pipeline_Viewer.py` — `render_inspector(view)` call line 97

**Fix approach:** Implement a Streamlit custom component or use `streamlit-javascript` bridge to pass the clicked node ID back as session state, then filter `render_inspector` by node.

---

### 15. Only one Alembic migration — no downgrade path tested

**Issue:** `alembic/versions/0001_initial_schema.py` implements `upgrade()`. The `downgrade()` function drops all tables. There is no test for the downgrade path, and no second migration has been written yet to validate the Alembic chain integrity.

**Files:**
- `alembic/versions/0001_initial_schema.py`

---

## Incomplete Features

| Feature | Status | Location |
|---|---|---|
| DB-backed Level 0 view projection | Not started | `src/scenario_db/view/service.py:241` |
| Level 1 IP DAG view | Not started | `src/scenario_db/view/service.py:245` |
| Level 2 composite-IP drill-down | Not started | `src/scenario_db/view/service.py:249` |
| ReviewGateEngine service | Not started | no file |
| Canonical graph builder | Not started | no file (`build_canonical_graph()` referenced only in docstring) |
| Variant resolver (capability → mode mapping) | Not started | no file |
| Persisted gate execution result table | Not started | no Alembic migration |
| SimEngine BW/Power/Perf integration | Not started | `docs/simulation-engine-integration.md` |
| Evidence Dashboard (Streamlit page) | Not started | `dashboard/Home.py:130` (disabled button) |
| Issue Explorer (Streamlit page) | Not started | `dashboard/Home.py:144` (disabled button) |
| Node click → inspector binding | Not started | `dashboard/components/elk_viewer.py:524` |
| `@lru_cache` on `match_issues_for_variant` | Deferred (Week 4) | `src/scenario_db/api/cache.py:91` |
| `mode=topology` view mode | Parameter accepted, not rendered | `src/scenario_db/api/routers/view.py:22` |

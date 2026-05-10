---
phase: 04-level0-viewer-db
reviewed: 2026-05-10T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - src/scenario_db/models/definition/usecase.py
  - src/scenario_db/view/service.py
  - dashboard/pages/1_Pipeline_Viewer.py
  - dashboard/components/elk_graph_builder.py
  - dashboard/components/elk_viewer.py
  - dashboard/components/node_detail_panel.py
  - tests/unit/test_pipeline_sw_stack.py
  - tests/unit/test_view_service.py
  - tests/integration/test_api_runtime.py
  - tests/integration/test_view_topology.py
findings:
  critical: 4
  warning: 6
  info: 3
  total: 13
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-05-10
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Phase 4 delivers the Level 0 pipeline viewer: a Streamlit dashboard backed by a FastAPI/PostgreSQL API.
Core functionality is complete and structurally sound, but the review surfaces four blocker-level
defects spanning security (user-controlled API URL injected into `requests` calls without validation),
correctness (NoResultFound raised where the router has no handler, duplicate topological sort
computation), and data integrity (silent fallback in `CATEGORY_TO_LANE` masks unknown categories
rather than surfacing them). Six additional warnings address robustness and code-quality gaps. Three
info items note style/coverage opportunities.

---

## Critical Issues

### CR-01: Unsanitized user-controlled API URL injected into `requests.get()` calls

**File:** `dashboard/pages/1_Pipeline_Viewer.py:159-166`

**Issue:** The `api_url` value is taken directly from a `st.text_input` widget (sidebar) and used
verbatim in `requests.get(f"{api_url}/api/v1/...")`. Because `@st.cache_data` is keyed on `api_url`,
an attacker with local access (or who can influence the session) can point the dashboard at any
internal host — including metadata endpoints on cloud infra (`http://169.254.169.254/...`), localhost
services on other ports, or SSRF-reachable internal APIs. There is no scheme whitelist, no hostname
validation, and no allow-list enforcement.

Additionally, the URL comparison on line 164 (`if api_url != st.session_state.get("api_url")`) runs
_before_ writing back to session state on line 168, meaning the very first load skips the cache-clear
branch even when the URL diverges from an unset default.

**Fix:**
```python
import urllib.parse

_ALLOWED_SCHEMES = {"http", "https"}
_ALLOWED_HOSTS = {"localhost", "127.0.0.1"}   # widen as needed for prod

def _validate_api_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"Scheme '{parsed.scheme}' not allowed")
    # Remove in prod if external hosts are required; keep for dev dashboards
    if parsed.hostname not in _ALLOWED_HOSTS:
        raise ValueError(f"Host '{parsed.hostname}' not in allow-list")
    return url.rstrip("/")

# In sidebar block:
raw_url = st.text_input("Base URL", value=..., ...)
try:
    api_url = _validate_api_url(raw_url)
except ValueError as e:
    st.sidebar.error(str(e))
    st.stop()
```

---

### CR-02: `service.py` raises `sqlalchemy.exc.NoResultFound` — not caught by the view router

**File:** `src/scenario_db/view/service.py:439-442`

**Issue:** `project_level0()` (DB path) raises `NoResultFound` when a scenario/variant is absent.
The `get_view` router in `view.py` wraps the call only in `except NotImplementedError`. The
application-level `_not_found_handler` (registered in `exceptions.py`) does catch `NoResultFound`
globally, so this _appears_ to work — but the intent expressed in the comment
`# WR-02 fix: replace NoResultFound with HTTPException(404)` (Phase 3 review history) was
specifically to avoid leaking ORM exceptions through service layer boundaries. In the current Phase 4
path the call crosses a service→router boundary that was fixed for _other_ endpoints but not this
one. If the global handler is ever removed or changed scope, this silently returns a 500.

Furthermore, `NoResultFound` is imported inside the function body (`from sqlalchemy.exc import
NoResultFound`) — coupling the service layer to SQLAlchemy semantics that should be confined to the
repository layer.

**Fix:**
```python
# In project_level0(), replace:
from sqlalchemy.exc import NoResultFound
projection = get_view_projection(db, scenario_id, variant_id)
if projection is None:
    raise NoResultFound(...)

# With:
from fastapi import HTTPException
projection = get_view_projection(db, scenario_id, variant_id)
if projection is None:
    raise HTTPException(
        status_code=404,
        detail=f"scenario '{scenario_id}' / variant '{variant_id}' not found",
    )
```

---

### CR-03: `_sw_stack_to_view_response()` calls `_projection_to_view_response()` redundantly — double topological sort executed per request

**File:** `src/scenario_db/view/service.py:380`

**Issue:** `_sw_stack_to_view_response()` calls `_projection_to_view_response(projection)` internally
to obtain the HW layout (line 380). `project_level0()` dispatches to `_sw_stack_to_view_response()`
for topology mode — meaning the topological sort (`graphlib.TopologicalSorter`) runs once inside
`_sw_stack_to_view_response` (via the nested call) and _would_ run again if topology mode ever
branched through architecture first. More critically, this design means any future caching of the
architecture result is bypassed silently. The bug surface: if `projection` in topology mode also
triggers `_projection_to_view_response`, then duplicate `NodeElement` objects for the same HW nodes
can appear in `all_nodes` (line 398) if the same node is listed in both `sw_stack` (with `ip_ref`
matching a HW node id) and `pipeline.nodes`. `sw_hw_edges` are built by checking membership in
`hw_node_ids`, which is derived from `hw_view.nodes` — but if a sw_stack node has an `id` that
collides with a pipeline HW node id, it will appear in both `sw_nodes` and `hw_view.nodes`, creating
a duplicate node id in the ELK graph. ELK's layered algorithm is sensitive to duplicate ids and may
throw a runtime error or produce malformed layout.

**Fix:**
```python
def _sw_stack_to_view_response(projection: dict) -> ViewResponse:
    hw_view = _projection_to_view_response(projection)
    hw_node_ids = {n.data.id for n in hw_view.nodes}

    sw_stack_raw = projection.get("pipeline", {}).get("sw_stack", [])
    sw_node_ids_used: set[str] = set()
    sw_nodes: list[NodeElement] = []
    ...
    for sw in sw_stack_raw:
        nid = sw.get("id", "")
        if not nid or nid in hw_node_ids:   # skip collision with HW ids
            continue
        ...
```

---

### CR-04: XSS via unescaped user-controlled data interpolated into `innerHTML` (`unsafe_allow_html=True`)

**File:** `dashboard/components/node_detail_panel.py:28-42`, `57-109`

**Issue:** `render_inspector()` and `_risk_card()` interpolate data fields from `ViewResponse` and
`RiskCard` directly into HTML strings rendered via `st.markdown(..., unsafe_allow_html=True)`:

```python
# node_detail_panel.py:29
f'<span ...>{risk.title}</span>'   # risk.title is user/DB data, not HTML-escaped
f'<span ...>{risk.component}</span>'
f'<span ...>{risk.description}</span>'
```

Similarly `s.name`, `s.subtitle`, `s.notes`, `s.captured_at`, `s.resolution`, `s.variant_label`
(lines 57-109) are all injected without escaping. If any of these fields contains a `<script>` tag
or `</div><script>...` payload (sourced from the database, a YAML fixture, or the API response),
the browser will execute it.

The same issue exists in `elk_viewer.py` (JS template side): `node.id`, `m.label`, `d.type`,
`d.ip_ref`, `d.scale`, `d.llc` are written into the tooltip via `tip.innerHTML = h` at line 380.
These values come from the ELK meta dict which originates from DB data.

**Fix:**
```python
import html as html_mod

def _escape(s: str | None) -> str:
    return html_mod.escape(str(s or ""))

# Replace all direct interpolation:
f'<span ...>{_escape(risk.title)}</span>'
f'<span ...>{_escape(risk.description)}</span>'
```

For the JS side in `elk_viewer.py`, replace `innerHTML` assignments with `textContent` where
possible, or use a DOM-building helper that does not accept raw HTML.

---

## Warnings

### WR-01: `CATEGORY_TO_LANE` fallback silently maps unknown categories to `"hw"` — masks data errors

**File:** `src/scenario_db/view/service.py:289`

**Issue:**
```python
lane = CATEGORY_TO_LANE.get(category, "hw")
```

If `ip_catalog` has a new category (e.g., `"isp"`, `"sensor"`, `"npu"`) not present in the four-
entry map, the node silently lands in the `"hw"` lane. This is the correct lane for _all_ current
categories, but the fallback on an empty string (line 288: `category = ip_info.get("category", "")`)
also maps unknowns to `"hw"` without any diagnostic. A node with a malformed/absent `ip_ref` is
indistinguishable from a correctly-categorized node in the resulting view.

`test_unknown_category_falls_back_to_hw` in `test_view_service.py` explicitly validates this silent
fallback as correct behavior, which means the test is encoding a silent failure as "expected."

**Fix:**
```python
lane = CATEGORY_TO_LANE.get(category)
if lane is None:
    # Log a warning; default to "hw" for now but surface the gap
    import logging
    logging.getLogger(__name__).warning(
        "Unknown ip_catalog category %r for node %r — defaulting to 'hw'", category, nid
    )
    lane = "hw"
```

Update `test_unknown_category_falls_back_to_hw` to assert a warning is emitted.

---

### WR-02: `@st.cache_data` TTL mismatch — variant list cached 2x longer than view data

**File:** `dashboard/pages/1_Pipeline_Viewer.py:109-141`

**Issue:** `_fetch_scenarios` and `_fetch_variants` use `ttl=60`, while `_load_view` also uses
`ttl=60` and `_fetch_gate` uses `ttl=30`. The variant list and scenario list are keyed on `api_url`
and `api_url + scenario_id` respectively. If a new variant is added to the DB, it will not appear
in the dropdown for up to 60 seconds — but the view data for that variant (if navigated to) will
also be stale. This asymmetry means the user could see "variant not found" errors for up to 60s
after a DB write. This is an availability gap, not a data-loss risk, but it can confuse operators.

More importantly: `_fetch_gate` has `ttl=30` but `_fetch_scenarios`/`_fetch_variants` have `ttl=60`.
After the scenario list refreshes and the user selects a new variant, the gate result for the
_previous_ variant may still be cached for up to 30s — incorrectly showing the previous gate state
for the newly selected variant. This is because `_fetch_gate` is keyed on
`(api_url, scenario_id, variant_id)`, so this is actually safe once the key changes. Clarifying
comment should be added.

**Fix:** Set `_fetch_scenarios` and `_fetch_variants` to `ttl=30` to match the gate TTL and avoid
the stale-dropdown window.

---

### WR-03: `requests.get()` has no `Session` — no connection pooling, no retry, no auth header injection

**File:** `dashboard/pages/1_Pipeline_Viewer.py:112, 121, 133, 146`

**Issue:** All four HTTP calls use bare `requests.get(...)`. Without a `requests.Session`, each call
opens a new TCP connection; there is no connection pool, no retry logic, and no shared auth header.
If the API requires a bearer token in the future, it must be added to four separate call sites.
`timeout=10` is present (good), but the `requests` library does not distinguish connect timeout from
read timeout with a single integer — a slow response body will block the Streamlit main thread for
10 seconds.

**Fix:**
```python
import requests

@st.cache_resource
def _api_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Accept": "application/json"})
    return s

# Use throughout:
r = _api_session().get(url, params=params, timeout=(5, 10))  # (connect, read)
```

---

### WR-04: `_render_html()` template substitution uses `str.replace()` — injection if JSON contains the sentinel string

**File:** `dashboard/components/elk_viewer.py:494-499`

**Issue:**
```python
html = html.replace("/*__GRAPH__*/", json.dumps(elk_graph, ensure_ascii=False))
html = html.replace("/*__META__*/",  json.dumps(meta,      ensure_ascii=False))
html = html.replace("/*__CANVAS_H__*/", str(canvas_h))
```

`json.dumps(elk_graph)` or `json.dumps(meta)` could in theory contain the literal string
`/*__META__*/` or `/*__CANVAS_H__*/` if a node id, label, or detail value contains that text (e.g.,
a label `"/*__META__*/"` in the DB). The first `replace` call substitutes `/*__GRAPH__*/`; the
result is then scanned again for `/*__META__*/`, which could match text _inside_ the already-
substituted JSON, breaking the template. `/*__CANVAS_H__*/` appears twice in the CSS height
declaration and once in the JS constant — `str.replace` replaces all occurrences, which is correct
here but is not obvious.

**Fix:** Use a unique sentinel that cannot appear in JSON (e.g., `__GRAPH_DATA_PLACEHOLDER__`
surrounded by characters illegal in JSON strings), or use `re.sub` with a count parameter to
replace only the first occurrence, or inline the data as a dedicated `<script>` block before the
main script. The safest approach:

```python
import re

_GRAPH_MARKER = '"__GRAPH_PLACEHOLDER__"'
_META_MARKER  = '"__META_PLACEHOLDER__"'

# Replace markers in template with actual JSON (markers are valid JSON string literals)
html = _HTML_TEMPLATE.replace(_GRAPH_MARKER, json.dumps(elk_graph, ensure_ascii=False), 1)
html = html.replace(_META_MARKER, json.dumps(meta, ensure_ascii=False), 1)
```

---

### WR-05: `topology` mode applies `_sw_stack_to_view_response()` when `db=None` falls back to `build_sample_level0()`

**File:** `src/scenario_db/view/service.py:435-447`

**Issue:**
```python
if db is None:
    return build_sample_level0()          # always architecture mode sample

if mode == "architecture":
    return _projection_to_view_response(projection)
else:  # topology
    return _sw_stack_to_view_response(projection)
```

When `db=None` (dashboard demo mode), topology mode silently returns the _architecture_ sample
response regardless of what the caller requested. The returned `ViewResponse.mode` field is
`"architecture"` (from `build_sample_level0()`), but the caller passed `mode="topology"`. The
Streamlit page uses `LAYERS[mode]` to filter visible layers (line 287); for topology mode this is
`["app","framework","hal","kernel","hw"]`. If the returned `ViewResponse` contains only `"hw"` and
`"memory"` layer nodes (architecture sample), the ELK graph will show an empty diagram for topology
mode in demo/offline mode.

**Fix:**
```python
if db is None:
    if mode == "topology":
        return _build_sample_topology()   # add a topology-mode sample, or
    return build_sample_level0()
```

At minimum, add a `# TODO` comment and ensure `ViewResponse.mode` matches the requested mode.

---

### WR-06: Integration tests hard-code `UHD60-HDR10-H265` variant id — may not exist in ETL fixture

**File:** `tests/integration/test_api_runtime.py:8`, `tests/integration/test_view_topology.py:14`

**Issue:** Both integration test files use `VARIANT_ID = "UHD60-HDR10-H265"` as a constant.
`test_view_architecture_mode` and `test_topology_view_*` all depend on this fixture being present
in the database after ETL. If the demo fixture YAML changes the variant id (e.g., to
`"FHD30-SDR-H265"` as used in `service.py`'s `build_sample_level0()`), every test in these files
will return 404 and fail with an unhelpful assertion error on `status_code`.

`test_api_runtime.py:17` asserts `data["variant_id"] == VARIANT_ID` — if the ETL loads a different
variant id, this will silently pass the HTTP 200 check but fail on the field assertion, giving a
confusing message.

**Fix:** Load the variant id dynamically from the API after ETL (e.g., GET `/scenarios/{id}/variants`
in a fixture), or add a conftest assertion that verifies the expected fixture variant exists before
the test suite runs.

---

## Info

### IN-01: `PipelineEdge` uses `BaseModel` directly instead of `BaseScenarioModel` — breaks `extra='forbid'` convention

**File:** `src/scenario_db/models/definition/usecase.py:35-42`

**Issue:** `PipelineEdge` explicitly sets `model_config = ConfigDict(extra="forbid", populate_by_name=True)`
which achieves the correct behavior. However, the project convention (CLAUDE.md) is that all Pydantic
models inherit from `BaseScenarioModel`, which already enforces `extra='forbid'`. `PipelineEdge`
cannot inherit from `BaseScenarioModel` _and_ add `populate_by_name=True` without overriding
`model_config` entirely — which is what it does. The override clobbers `BaseScenarioModel`'s config
in full; if `BaseScenarioModel` ever gains additional config options, `PipelineEdge` will silently
drop them.

**Fix:** Either inherit from `BaseScenarioModel` and use `model_config = ConfigDict(extra="forbid", populate_by_name=True)` (as currently done — this is acceptable), or add a comment explicitly
justifying the deviation from the convention so reviewers do not introduce a regression.

---

### IN-02: `console.log` left in production JS renderer

**File:** `dashboard/components/elk_viewer.py:470`

**Issue:**
```javascript
console.log('[ELK] layout done W='+W+' H='+H+
  ' nodes='+(layout.children||[]).length+
  ' edges='+(layout.edges||[]).length);
```

This is visible in browser dev-tools in all deployments. Not a security risk, but it is debug output
in shipped code.

**Fix:** Remove or gate behind a `DEBUG` flag (e.g., only emit if a `?debug=1` query param is
present in the URL).

---

### IN-03: `test_pipeline_sw_stack.py` does not test `extra='forbid'` enforcement on `SwStackNode`

**File:** `tests/unit/test_pipeline_sw_stack.py`

**Issue:** `SwStackNode` inherits from `BaseScenarioModel` (which enforces `extra='forbid'`), but no
test verifies this. A test for an unknown field like `{"layer": "hal", "id": "x", "label": "X", "unknown_field": "oops"}` should raise `ValidationError`. This is part of the required test
coverage per CLAUDE.md ("모든 Pydantic 모델에 pytest fixture + round-trip test 작성").

**Fix:**
```python
def test_sw_stack_node_rejects_extra_fields():
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        SwStackNode(layer="hal", id="x", label="X", unknown_field="oops")
```

---

_Reviewed: 2026-05-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

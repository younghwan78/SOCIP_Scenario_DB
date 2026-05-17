"""Phase 7 — /simulation/ 엔드포인트 통합 테스트 (SAPI-01~06, D-11).

TestClient + PostgreSQL 컨테이너 (기존 conftest.py api_client 픽스처 재사용).

전략:
  - run_simulation()은 monkeypatch로 고정 SimRunResult 반환 → DVFS YAML 의존성 없이 테스트
  - load_runner_inputs_from_db()도 monkeypatch → DB에 demo variant sim_config/sim_port_config
    미설정이어도 테스트 가능
  - save_sim_evidence() / find_by_params_hash()는 실제 DB 사용 → 캐싱 플로우 실제 검증

테스트 목록 (최소 8개):
  1. test_post_run_cache_miss — 첫 번째 POST: cached=False, evidence_id 반환
  2. test_post_run_cache_hit — 동일 payload 두 번째 POST: cached=True, 동일 evidence_id 반환
  3. test_get_results — GET /results/{id}: 200, dma_breakdown/timing_breakdown 키 존재
  4. test_get_results_not_found — GET /results/nonexistent: 404
  5. test_bw_analysis_sorted — GET /bw-analysis: 200, ports bw_mbs 내림차순 검증
  6. test_bw_analysis_not_found — 없는 evidence_id: 404
  7. test_power_analysis — GET /power-analysis: 200, per_ip/per_vdd/bw_power_mw 키 존재
  8. test_timing_analysis — GET /timing-analysis: 200, critical_ip/feasible/hw_time_max_ms 존재
  9. test_run_invalid_scenario — 없는 scenario_id: 404
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from scenario_db.models.evidence.simulation import IPTimingResult, PortBWResult
from scenario_db.sim.models import SimRunResult

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# 공통 상수 + 픽스처 SimRunResult
# ---------------------------------------------------------------------------

# 테스트용 고정 SimRunResult (DVFS 계산 없이 monkeypatch)
FIXED_DMA_BREAKDOWN = [
    PortBWResult(ip="ISP", port="rd0", direction="read",  bw_mbs=3200.0, bw_power_mw=128.0),
    PortBWResult(ip="MFC", port="rd0", direction="read",  bw_mbs=1800.0, bw_power_mw=72.0),
    PortBWResult(ip="ISP", port="wr0", direction="write", bw_mbs=2400.0, bw_power_mw=96.0),
]

FIXED_TIMING_BREAKDOWN = [
    IPTimingResult(
        ip="ISP",
        hw_time_ms=15.2,
        required_clock_mhz=664.0,
        set_clock_mhz=700.0,
        set_voltage_mv=780.0,
        feasible=True,
    ),
    IPTimingResult(
        ip="MFC",
        hw_time_ms=12.5,
        required_clock_mhz=350.0,
        set_clock_mhz=400.0,
        set_voltage_mv=750.0,
        feasible=True,
    ),
]

FIXED_SIM_RESULT = SimRunResult(
    scenario_id="uc-camera-recording",
    variant_id="UHD60-HDR10-H265",
    total_power_mw=1250.0,
    total_power_ma=367.6,
    bw_total_mbs=7400.0,
    hw_time_max_ms=15.2,
    feasible=True,
    dma_breakdown=FIXED_DMA_BREAKDOWN,
    timing_breakdown=FIXED_TIMING_BREAKDOWN,
    vdd_power={"VDD_CAM": 800.0, "VDD_MIF": 450.0},
    ip_power={"ISP": 700.0, "MFC": 300.0},
)

# demo fixture에 있는 scenario/variant ID
SCENARIO_ID = "uc-camera-recording"
VARIANT_ID = "UHD60-HDR10-H265"
BASE_URL = "/api/v1/simulation"

# monkeypatch target paths
RUNNER_PATH = "scenario_db.api.routers.simulation.run_simulation"
LOADER_PATH = "scenario_db.api.routers.simulation.load_runner_inputs_from_db"


def _make_fake_loader():
    """load_runner_inputs_from_db monkeypatch용 — None 아닌 6-튜플 반환."""
    from scenario_db.models.definition.usecase import (
        IPPortConfig,
        Pipeline,
        SimGlobalConfig,
    )
    pipeline = Pipeline(nodes=[], edges=[])
    ip_catalog = {}
    dvfs_tables = {}
    variant_port_config: dict[str, IPPortConfig] = {}
    sim_config = SimGlobalConfig()
    sensor_spec = None
    return pipeline, ip_catalog, dvfs_tables, variant_port_config, sim_config, sensor_spec


# ---------------------------------------------------------------------------
# 1. POST /simulation/run — cache MISS (첫 번째 호출)
# ---------------------------------------------------------------------------

def test_post_run_cache_miss(api_client: TestClient, monkeypatch):
    """POST /simulation/run → 첫 번째 호출: cached=False, evidence_id 반환 (SAPI-01)."""
    monkeypatch.setattr(RUNNER_PATH, lambda **kw: FIXED_SIM_RESULT)
    monkeypatch.setattr(LOADER_PATH, lambda db, sid, vid: _make_fake_loader())

    payload = {
        "scenario_id": SCENARIO_ID,
        "variant_id": VARIANT_ID,
        "fps": 30.0,
        "asv_group": 4,
    }
    resp = api_client.post(f"{BASE_URL}/run", json=payload)
    assert resp.status_code == 200, resp.text

    data = resp.json()
    assert data["cached"] is False
    assert data["evidence_id"].startswith("evd-sim-")
    assert len(data["params_hash"]) == 64      # SHA256 hex
    assert data["feasible"] is True
    assert data["total_power_mw"] == pytest.approx(1250.0)
    assert data["bw_total_mbs"] == pytest.approx(7400.0)
    assert data["hw_time_max_ms"] == pytest.approx(15.2)


# ---------------------------------------------------------------------------
# 2. POST /simulation/run — cache HIT (두 번째 동일 payload)
# ---------------------------------------------------------------------------

def test_post_run_cache_miss_and_hit(api_client: TestClient, monkeypatch):
    """동일 payload 두 번째 POST → cached=True, 동일 evidence_id 반환 (SAPI-06)."""
    monkeypatch.setattr(RUNNER_PATH, lambda **kw: FIXED_SIM_RESULT)
    monkeypatch.setattr(LOADER_PATH, lambda db, sid, vid: _make_fake_loader())

    payload = {
        "scenario_id": SCENARIO_ID,
        "variant_id": VARIANT_ID,
        "fps": 60.0,   # fps 달리해서 이전 테스트 캐시와 충돌 방지
        "asv_group": 4,
    }

    resp1 = api_client.post(f"{BASE_URL}/run", json=payload)
    assert resp1.status_code == 200, resp1.text
    data1 = resp1.json()
    assert data1["cached"] is False
    first_evidence_id = data1["evidence_id"]

    resp2 = api_client.post(f"{BASE_URL}/run", json=payload)
    assert resp2.status_code == 200, resp2.text
    data2 = resp2.json()
    assert data2["cached"] is True
    assert data2["evidence_id"] == first_evidence_id   # 동일 evidence 반환


# ---------------------------------------------------------------------------
# 3. GET /simulation/results/{evidence_id} — 200, 키 존재 확인
# ---------------------------------------------------------------------------

def test_get_results(api_client: TestClient, monkeypatch):
    """GET /simulation/results/{evidence_id} → 200, dma_breakdown + timing_breakdown 키 포함 (SAPI-02)."""
    monkeypatch.setattr(RUNNER_PATH, lambda **kw: FIXED_SIM_RESULT)
    monkeypatch.setattr(LOADER_PATH, lambda db, sid, vid: _make_fake_loader())

    # POST run → evidence_id 획득
    payload = {
        "scenario_id": SCENARIO_ID,
        "variant_id": VARIANT_ID,
        "fps": 45.0,   # 고유 fps로 새 evidence 생성
        "asv_group": 4,
    }
    post_resp = api_client.post(f"{BASE_URL}/run", json=payload)
    assert post_resp.status_code == 200
    evidence_id = post_resp.json()["evidence_id"]

    # GET results
    resp = api_client.get(f"{BASE_URL}/results/{evidence_id}")
    assert resp.status_code == 200, resp.text

    data = resp.json()
    assert "dma_breakdown" in data
    assert "timing_breakdown" in data
    assert "kpi" in data
    assert data["id"] == evidence_id
    assert data["kind"] == "evidence.simulation"
    assert isinstance(data["dma_breakdown"], list)
    assert isinstance(data["timing_breakdown"], list)
    assert len(data["dma_breakdown"]) == 3   # FIXED_DMA_BREAKDOWN 3개
    assert len(data["timing_breakdown"]) == 2   # FIXED_TIMING_BREAKDOWN 2개


# ---------------------------------------------------------------------------
# 4. GET /simulation/results/nonexistent → 404
# ---------------------------------------------------------------------------

def test_get_results_not_found(api_client: TestClient):
    """존재하지 않는 evidence_id → 404 (SAPI-02 오류 경로)."""
    resp = api_client.get(f"{BASE_URL}/results/nonexistent-evidence-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 5. GET /simulation/bw-analysis — 200, bw_mbs 내림차순 정렬 검증
# ---------------------------------------------------------------------------

def test_bw_analysis_sorted(api_client: TestClient, monkeypatch):
    """GET /simulation/bw-analysis → ports bw_mbs 내림차순 정렬 (SAPI-03, D-05)."""
    monkeypatch.setattr(RUNNER_PATH, lambda **kw: FIXED_SIM_RESULT)
    monkeypatch.setattr(LOADER_PATH, lambda db, sid, vid: _make_fake_loader())

    payload = {
        "scenario_id": SCENARIO_ID,
        "variant_id": VARIANT_ID,
        "fps": 50.0,
        "asv_group": 4,
    }
    post_resp = api_client.post(f"{BASE_URL}/run", json=payload)
    assert post_resp.status_code == 200
    evidence_id = post_resp.json()["evidence_id"]

    resp = api_client.get(f"{BASE_URL}/bw-analysis", params={"evidence_id": evidence_id})
    assert resp.status_code == 200, resp.text

    data = resp.json()
    assert data["evidence_id"] == evidence_id
    assert "ports" in data
    assert "total_bw_mbs" in data

    ports = data["ports"]
    assert len(ports) == 3   # FIXED_DMA_BREAKDOWN 3개

    # bw_mbs 내림차순 검증
    for i in range(len(ports) - 1):
        assert ports[i]["bw_mbs"] >= ports[i + 1]["bw_mbs"], (
            f"ports[{i}].bw_mbs={ports[i]['bw_mbs']} < ports[{i+1}].bw_mbs={ports[i+1]['bw_mbs']} — 정렬 오류"
        )

    # total_bw_mbs = 3200 + 2400 + 1800 = 7400
    assert data["total_bw_mbs"] == pytest.approx(7400.0)


# ---------------------------------------------------------------------------
# 6. GET /simulation/bw-analysis — 없는 evidence_id → 404
# ---------------------------------------------------------------------------

def test_bw_analysis_not_found(api_client: TestClient):
    """존재하지 않는 evidence_id → 404 (SAPI-03 오류 경로)."""
    resp = api_client.get(f"{BASE_URL}/bw-analysis", params={"evidence_id": "nonexistent-bw-id"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 7. GET /simulation/power-analysis — 200, per_ip/per_vdd/bw_power_mw 키 존재
# ---------------------------------------------------------------------------

def test_power_analysis(api_client: TestClient, monkeypatch):
    """GET /simulation/power-analysis → per_ip/per_vdd/bw_power_mw 포함 (SAPI-04)."""
    monkeypatch.setattr(RUNNER_PATH, lambda **kw: FIXED_SIM_RESULT)
    monkeypatch.setattr(LOADER_PATH, lambda db, sid, vid: _make_fake_loader())

    payload = {
        "scenario_id": SCENARIO_ID,
        "variant_id": VARIANT_ID,
        "fps": 25.0,
        "asv_group": 4,
    }
    post_resp = api_client.post(f"{BASE_URL}/run", json=payload)
    assert post_resp.status_code == 200
    evidence_id = post_resp.json()["evidence_id"]

    resp = api_client.get(f"{BASE_URL}/power-analysis", params={"evidence_id": evidence_id})
    assert resp.status_code == 200, resp.text

    data = resp.json()
    assert data["evidence_id"] == evidence_id
    assert "total_power_mw" in data
    assert "total_power_ma" in data
    assert "per_ip" in data
    assert "per_vdd" in data
    assert "bw_power_mw" in data

    assert data["total_power_mw"] == pytest.approx(1250.0)
    assert isinstance(data["per_ip"], dict)
    assert isinstance(data["per_vdd"], dict)

    # per_ip는 ip_breakdown.ip_power — ISP, MFC 포함
    assert "ISP" in data["per_ip"]
    assert "MFC" in data["per_ip"]
    assert data["per_ip"]["ISP"] == pytest.approx(700.0)

    # bw_power_mw = 128 + 72 + 96 = 296
    assert data["bw_power_mw"] == pytest.approx(296.0)


# ---------------------------------------------------------------------------
# 8. GET /simulation/timing-analysis — 200, critical_ip/feasible/hw_time_max_ms 존재
# ---------------------------------------------------------------------------

def test_timing_analysis(api_client: TestClient, monkeypatch):
    """GET /simulation/timing-analysis → critical_ip/feasible/hw_time_max_ms 포함 (SAPI-05)."""
    monkeypatch.setattr(RUNNER_PATH, lambda **kw: FIXED_SIM_RESULT)
    monkeypatch.setattr(LOADER_PATH, lambda db, sid, vid: _make_fake_loader())

    payload = {
        "scenario_id": SCENARIO_ID,
        "variant_id": VARIANT_ID,
        "fps": 20.0,
        "asv_group": 4,
    }
    post_resp = api_client.post(f"{BASE_URL}/run", json=payload)
    assert post_resp.status_code == 200
    evidence_id = post_resp.json()["evidence_id"]

    resp = api_client.get(f"{BASE_URL}/timing-analysis", params={"evidence_id": evidence_id})
    assert resp.status_code == 200, resp.text

    data = resp.json()
    assert data["evidence_id"] == evidence_id
    assert "feasible" in data
    assert "hw_time_max_ms" in data
    assert "critical_ip" in data
    assert "per_ip" in data

    assert data["feasible"] is True
    assert data["hw_time_max_ms"] == pytest.approx(15.2)
    assert data["critical_ip"] == "ISP"  # FIXED_TIMING_BREAKDOWN에서 최대 hw_time_ms

    per_ip = data["per_ip"]
    assert len(per_ip) == 2   # ISP + MFC
    # hw_time_ms 내림차순 — 첫 번째가 ISP (15.2ms > 12.5ms)
    assert per_ip[0]["ip"] == "ISP"
    assert per_ip[0]["hw_time_ms"] == pytest.approx(15.2)
    assert per_ip[1]["ip"] == "MFC"


# ---------------------------------------------------------------------------
# 9. POST /simulation/run — 없는 scenario_id → 404
# ---------------------------------------------------------------------------

def test_run_invalid_scenario(api_client: TestClient):
    """존재하지 않는 scenario_id로 POST /run → 404 (load_runner_inputs_from_db returns None)."""
    payload = {
        "scenario_id": "no-such-scenario-xyz",
        "variant_id": "no-such-variant-xyz",
        "fps": 30.0,
    }
    resp = api_client.post(f"{BASE_URL}/run", json=payload)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 10. GET /simulation/timing-analysis — 없는 evidence_id → 404
# ---------------------------------------------------------------------------

def test_timing_analysis_not_found(api_client: TestClient):
    """존재하지 않는 evidence_id → 404 (SAPI-05 오류 경로)."""
    resp = api_client.get(
        f"{BASE_URL}/timing-analysis", params={"evidence_id": "nonexistent-timing-id"}
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 11. GET /simulation/power-analysis — 없는 evidence_id → 404
# ---------------------------------------------------------------------------

def test_power_analysis_not_found(api_client: TestClient):
    """존재하지 않는 evidence_id → 404 (SAPI-04 오류 경로)."""
    resp = api_client.get(
        f"{BASE_URL}/power-analysis", params={"evidence_id": "nonexistent-power-id"}
    )
    assert resp.status_code == 404

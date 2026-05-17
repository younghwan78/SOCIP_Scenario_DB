"""tests/unit/test_loaders.py — db/loaders.py 단위 테스트 (Phase 7, D-02, D-03, D-07).

TDD RED 단계: loaders.py 미구현 상태에서 실패 확인 후 GREEN 단계 진행.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scenario_db.api.schemas.simulation import SimulateRequest
from scenario_db.models.definition.usecase import SimGlobalConfig


# ---------------------------------------------------------------------------
# compute_params_hash 테스트
# ---------------------------------------------------------------------------


class TestComputeParamsHash:
    """compute_params_hash() — SHA256 결정론적 해시 (D-02)."""

    def test_returns_64_char_hex(self) -> None:
        """반환값은 SHA256 hex digest — 64자 hex string."""
        from scenario_db.db.loaders import compute_params_hash

        req = SimulateRequest(scenario_id="s1", variant_id="v1", fps=30.0)
        result = compute_params_hash(req)
        assert isinstance(result, str)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic_same_input(self) -> None:
        """동일 입력 → 동일 해시 (여러 번 호출해도 같은 값)."""
        from scenario_db.db.loaders import compute_params_hash

        req = SimulateRequest(scenario_id="s1", variant_id="v1", fps=30.0)
        h1 = compute_params_hash(req)
        h2 = compute_params_hash(req)
        assert h1 == h2

    def test_sort_keys_independent_of_dict_order(self) -> None:
        """dvfs_overrides 딕셔너리 키 순서가 달라도 동일 해시 (sort_keys=True)."""
        from scenario_db.db.loaders import compute_params_hash

        req1 = SimulateRequest(
            scenario_id="s1", variant_id="v1", fps=30.0,
            dvfs_overrides={"cam": 1, "isp": 2},
        )
        req2 = SimulateRequest(
            scenario_id="s1", variant_id="v1", fps=30.0,
            dvfs_overrides={"isp": 2, "cam": 1},
        )
        assert compute_params_hash(req1) == compute_params_hash(req2)

    def test_different_scenario_id_different_hash(self) -> None:
        """다른 scenario_id → 다른 해시."""
        from scenario_db.db.loaders import compute_params_hash

        req_a = SimulateRequest(scenario_id="s1", variant_id="v1", fps=30.0)
        req_b = SimulateRequest(scenario_id="s2", variant_id="v1", fps=30.0)
        assert compute_params_hash(req_a) != compute_params_hash(req_b)

    def test_different_fps_different_hash(self) -> None:
        """다른 fps → 다른 해시."""
        from scenario_db.db.loaders import compute_params_hash

        req_a = SimulateRequest(scenario_id="s1", variant_id="v1", fps=30.0)
        req_b = SimulateRequest(scenario_id="s1", variant_id="v1", fps=60.0)
        assert compute_params_hash(req_a) != compute_params_hash(req_b)

    def test_different_asv_group_different_hash(self) -> None:
        """다른 asv_group → 다른 해시."""
        from scenario_db.db.loaders import compute_params_hash

        req_a = SimulateRequest(scenario_id="s1", variant_id="v1", asv_group=4)
        req_b = SimulateRequest(scenario_id="s1", variant_id="v1", asv_group=8)
        assert compute_params_hash(req_a) != compute_params_hash(req_b)


# ---------------------------------------------------------------------------
# apply_request_overrides 테스트
# ---------------------------------------------------------------------------


class TestApplyRequestOverrides:
    """apply_request_overrides() — DB sim_config + request override (D-03)."""

    def _default_sim_config(self) -> SimGlobalConfig:
        return SimGlobalConfig(
            asv_group=4,
            sw_margin=0.25,
            bw_power_coeff=80.0,
            vbat=4.0,
            pmic_eff=0.85,
            h_blank_margin=0.05,
            dvfs_overrides={"old_key": 2},
        )

    def test_asv_group_replaced_by_request(self) -> None:
        """req.asv_group이 sim_config.asv_group을 교체한다."""
        from scenario_db.db.loaders import apply_request_overrides

        sim_config = self._default_sim_config()
        req = SimulateRequest(scenario_id="s", variant_id="v", asv_group=8)
        result = apply_request_overrides(sim_config, req)
        assert result.asv_group == 8

    def test_dvfs_overrides_none_preserves_existing(self) -> None:
        """req.dvfs_overrides=None 이면 DB의 dvfs_overrides 값이 유지된다."""
        from scenario_db.db.loaders import apply_request_overrides

        sim_config = self._default_sim_config()
        req = SimulateRequest(scenario_id="s", variant_id="v", dvfs_overrides=None)
        result = apply_request_overrides(sim_config, req)
        assert result.dvfs_overrides == {"old_key": 2}

    def test_dvfs_overrides_replaced_when_provided(self) -> None:
        """req.dvfs_overrides가 있으면 DB 값을 교체한다."""
        from scenario_db.db.loaders import apply_request_overrides

        sim_config = self._default_sim_config()
        req = SimulateRequest(
            scenario_id="s", variant_id="v",
            dvfs_overrides={"cam": 3},
        )
        result = apply_request_overrides(sim_config, req)
        assert result.dvfs_overrides == {"cam": 3}

    def test_other_fields_preserved(self) -> None:
        """sw_margin, bw_power_coeff 등 기타 필드는 DB 값 유지."""
        from scenario_db.db.loaders import apply_request_overrides

        sim_config = self._default_sim_config()
        req = SimulateRequest(scenario_id="s", variant_id="v", asv_group=8)
        result = apply_request_overrides(sim_config, req)
        assert result.sw_margin == 0.25
        assert result.bw_power_coeff == 80.0
        assert result.vbat == 4.0
        assert result.pmic_eff == 0.85
        assert result.h_blank_margin == 0.05

    def test_returns_new_sim_global_config_instance(self) -> None:
        """원본 sim_config는 변경되지 않고 새 인스턴스 반환."""
        from scenario_db.db.loaders import apply_request_overrides

        sim_config = self._default_sim_config()
        req = SimulateRequest(scenario_id="s", variant_id="v", asv_group=8)
        result = apply_request_overrides(sim_config, req)
        # 원본은 변경 안됨
        assert sim_config.asv_group == 4
        # 새 인스턴스
        assert result is not sim_config
        assert isinstance(result, SimGlobalConfig)


# ---------------------------------------------------------------------------
# load_runner_inputs_from_db — None 반환 케이스 (Mock 기반)
# ---------------------------------------------------------------------------


class TestLoadRunnerInputsFromDbNoneCases:
    """load_runner_inputs_from_db() — scenario/variant 없음 시 None 반환 (D-07)."""

    def test_returns_none_when_scenario_not_found(self) -> None:
        """scenario가 DB에 없으면 None 반환."""
        from scenario_db.db.loaders import load_runner_inputs_from_db

        mock_db = MagicMock()
        # db.query(Scenario).filter_by(id=...).one_or_none() → None
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.one_or_none.return_value = None

        result = load_runner_inputs_from_db(mock_db, "nonexistent-scenario", "v1")
        assert result is None

    def test_returns_none_when_variant_not_found(self) -> None:
        """scenario는 있지만 variant가 없으면 None 반환."""
        from scenario_db.db.loaders import load_runner_inputs_from_db
        from scenario_db.db.models.definition import Scenario as ScenarioORM

        mock_db = MagicMock()
        # 1차 query (Scenario) → 시나리오 row 반환
        mock_scenario = MagicMock(spec=ScenarioORM)
        mock_scenario.id = "s1"
        mock_scenario.pipeline = {"nodes": [], "edges": []}
        mock_scenario.sensor = None

        call_count = 0

        def side_effect(model_cls):
            nonlocal call_count
            call_count += 1
            q = MagicMock()
            q.filter_by.return_value = q
            q.filter.return_value = q
            q.all.return_value = []
            if call_count == 1:
                # Scenario query
                q.one_or_none.return_value = mock_scenario
            else:
                # ScenarioVariant query → None
                q.one_or_none.return_value = None
            return q

        mock_db.query.side_effect = side_effect

        result = load_runner_inputs_from_db(mock_db, "s1", "nonexistent-variant")
        assert result is None

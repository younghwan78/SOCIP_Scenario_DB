from __future__ import annotations

import pytest

from scenario_db.sim.constants import (
    BPP_MAP,
    BW_POWER_COEFF_DEFAULT,
    REFERENCE_FPS,
    REFERENCE_VOLTAGE_MV,
)


@pytest.mark.parametrize("fmt,expected", [
    ("NV12", 1.5),
    ("YUV420", 1.5),
    ("RAW10", 1.25),
    ("ARGB", 4.0),
    ("BAYER", 1.0),
])
def test_bpp_map_values(fmt: str, expected: float) -> None:
    assert BPP_MAP[fmt] == expected, f"BPP_MAP[{fmt!r}] should be {expected}, got {BPP_MAP[fmt]}"


def test_reference_constants() -> None:
    assert REFERENCE_VOLTAGE_MV == 710.0
    assert REFERENCE_FPS == 30.0
    assert BW_POWER_COEFF_DEFAULT == 80.0

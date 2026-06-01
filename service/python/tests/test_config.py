"""Stage 0 smoke: config loads, validates, and exposes derived values."""

import pytest

from noircode.config import DEFAULT, MAX_PAYLOAD_LEN, Config


def test_default_config_is_valid() -> None:
    assert DEFAULT.grid_cells == DEFAULT.grid_cols * DEFAULT.grid_rows
    assert DEFAULT.bits_per_cell == 2  # tonal_levels=4 -> 2 bits
    assert MAX_PAYLOAD_LEN == 65535


@pytest.mark.parametrize(
    "kwargs",
    [
        {"tonal_levels": 1},
        {"tonal_margin": 0.5},
        {"rs_parity_ratio": 0.0},
        {"rs_parity_ratio": 1.0},
        {"grid_cols": 0},
    ],
)
def test_invalid_config_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        Config(**kwargs)  # type: ignore[arg-type]

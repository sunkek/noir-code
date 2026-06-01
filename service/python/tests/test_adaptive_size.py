"""Adaptive grid sizing: encoder picks the smallest version, decoder auto-detects it.

The panel's grid version is not signalled; the decoder trials the version ladder and
the frame CRC validates the right (version, rotation) pair. Short text -> smaller panel.
"""

import numpy as np
import pytest

from noircode.config import (
    FRAME_OVERHEAD_BYTES,
    GRID_VERSIONS,
    Config,
    select_grid,
    version_configs,
)
from noircode.decode.decoder import decode
from noircode.encode.encoder import encode
from noircode.geometry import layout
from noircode.simulate import warp_panel


def test_select_grid_picks_smallest_that_fits() -> None:
    base = Config()
    for cfg in version_configs(base):
        cap = cfg.rs_data_bytes - FRAME_OVERHEAD_BYTES
        # A payload that exactly fills this version must select it (or smaller never fits).
        chosen = select_grid(cap, base)
        assert chosen.grid_rows <= cfg.grid_rows
        assert chosen.rs_data_bytes - FRAME_OVERHEAD_BYTES >= cap


def test_select_grid_overflow_falls_back_to_largest() -> None:
    base = Config()
    huge = 10_000
    assert select_grid(huge, base).grid_rows == max(GRID_VERSIONS)


@pytest.mark.parametrize("text", ["", "hi", "https://example.com/p?q=1", "a" * 55, "a" * 173])
def test_adaptive_roundtrip(text: str) -> None:
    panel = encode(text, adaptive=True)
    assert decode(panel).text == text


def test_adaptive_shrinks_panel_for_short_text() -> None:
    small = encode("hi", adaptive=True)
    full = encode("a" * 173, adaptive=True)
    assert small.shape[0] < full.shape[0]
    # The big payload should match the default (largest) version's canonical size.
    assert full.shape[0] == layout(Config()).height


@pytest.mark.parametrize("text", ["hi", "a" * 55, "a" * 173])
def test_adaptive_survives_warp(text: str) -> None:
    panel = encode(text, style=True, adaptive=True)
    warped = warp_panel(panel, np.random.default_rng(7), blur=3, noise_sigma=5.0)
    assert decode(warped).text == text


def test_default_decode_still_reads_fixed_grid() -> None:
    # Non-adaptive (fixed 40x40) panels keep decoding unchanged.
    panel = encode("fixed grid stays")
    assert decode(panel).text == "fixed grid stays"

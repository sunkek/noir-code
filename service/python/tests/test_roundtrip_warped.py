"""Stage 2 gate: text -> panel -> synthetic warp -> rectify -> text, exact match.

Modest perspective warp, rotation, blur and noise. No Reed-Solomon yet, so the
finder detection + rectification must be good enough that Channel A reads back clean.
"""

import numpy as np
import pytest

from _capture import warp_panel
from noircode.config import Config
from noircode.decode.decoder import decode
from noircode.decode.detect import detect_and_rectify
from noircode.encode.encoder import encode


def test_clean_panel_decodes() -> None:
    panel = encode("noir", Config())
    res = decode(panel)
    assert res.ok and res.text == "noir"
    assert res.rotation == 0


@pytest.mark.parametrize("text", ["x", "hello", "The quick brown fox.", "rain on 5th st"])
def test_warped_roundtrip(text: str) -> None:
    cfg = Config()
    panel = encode(text, cfg)
    for seed in range(6):
        rng = np.random.default_rng(seed)
        captured = warp_panel(panel, rng)
        res = decode(captured, cfg)
        assert res.ok, f"decode failed (seed={seed}): {res.failed_stage}"
        assert res.text == text


@pytest.mark.parametrize("k", [0, 1, 2, 3])
def test_rotation_disambiguation(k: int) -> None:
    cfg = Config()
    panel = encode("orientation", cfg)
    rotated = np.rot90(panel, k)
    res = decode(rotated, cfg)
    assert res.ok and res.text == "orientation"


def test_rectify_recovers_canonical_size() -> None:
    cfg = Config()
    panel = encode("size", cfg)
    region = detect_and_rectify(panel, cfg)
    assert region.shape == (cfg.grid_rows * cfg.cell_px, cfg.grid_cols * cfg.cell_px)

"""Stage 4 gate: dual-channel decode + cross-channel checksum (border-frame layout).

Channel B is the bottom tonal-module strip ("frame line").

- clean panels decode with both channels agreeing;
- Channel B fills the header so a header-erased Channel A still recovers;
- erasing Channel B leaves Channel A self-sufficient;
- a tampered Channel B checksum is detected (cross_check False), never silently wrong.
"""

import numpy as np
import pytest

from _capture import warp_panel
from noircode.config import Config
from noircode.decode.decoder import decode
from noircode.encode.encoder import encode
from noircode.encode.grid import level_to_gray
from noircode.geometry import layout

_BOUNDARY_GRAY = 42  # between level 0 and 1 -> lands in the guard band -> erasure


def test_clean_dual_channel() -> None:
    cfg = Config()
    panel = encode("dual channel", cfg)
    res = decode(panel, cfg)
    assert res.ok and res.text == "dual channel"
    assert res.motif_erasures == 0
    assert res.cross_check is True


@pytest.mark.parametrize("text", ["x", "midnight rain", "blinds cast shadows"])
def test_warped_dual_channel(text: str) -> None:
    cfg = Config()
    panel = encode(text, cfg)
    for seed in range(4):
        rng = np.random.default_rng(seed)
        res = decode(warp_panel(panel, rng), cfg)
        assert res.ok and res.text == text


def test_channel_b_recovers_erased_header() -> None:
    cfg = Config()
    text = "header from strip"
    panel = encode(text, cfg)
    p = layout(cfg)
    # Erase the top-left grid corner (header codeword bytes) into the guard band.
    gx0, gy0, _, _ = p.grid_box
    panel[gy0 : gy0 + 3 * cfg.cell_px, gx0 : gx0 + 8 * cfg.cell_px] = _BOUNDARY_GRAY
    res = decode(panel, cfg)
    assert res.ok and res.text == text


def test_channel_a_self_sufficient_when_b_erased() -> None:
    cfg = Config()
    text = "grid alone"
    panel = encode(text, cfg)
    p = layout(cfg)
    for x0, y0, x1, y1 in p.strip_boxes:
        panel[y0:y1, x0:x1] = _BOUNDARY_GRAY  # all Channel B modules -> erasures
    res = decode(panel, cfg)
    assert res.ok and res.text == text
    assert res.motif_erasures == cfg.motif_count
    assert res.cross_check is None  # checksum unreadable


def test_cross_channel_disagreement_detected() -> None:
    cfg = Config()
    panel = encode("tampered", cfg)
    p = layout(cfg)
    # Flip the last strip module (a checksum nibble) to a different tonal level.
    x0, y0, x1, y1 = p.strip_boxes[-1]
    cur = int(round(float(panel[y0:y1, x0:x1].mean())))
    other = 0 if cur > 128 else cfg.motif_alphabet_size - 1
    panel[y0:y1, x0:x1] = level_to_gray(other, cfg.motif_alphabet_size)
    res = decode(panel, cfg)
    assert res.ok and res.text == "tampered"  # Channel A still correct
    assert res.cross_check is False
    assert res.confidence < 1.0

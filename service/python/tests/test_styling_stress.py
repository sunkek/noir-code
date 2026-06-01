"""Stage 5 gate: every prior gate still passes with full noir styling applied.

Styling must respect the tonal-level margins and motif legibility budget. If a styled
panel breaks decode, that is a styling bug.
"""

import numpy as np
import pytest

from _capture import jpeg, occlude_grid, warp_panel
from noircode.config import Config
from noircode.decode.decoder import decode
from noircode.encode.encoder import encode


def _styled(text: str, cfg: Config) -> np.ndarray:
    return encode(text, cfg, style=True)


@pytest.mark.parametrize("text", ["", "x", "hello", "neon noir, 3am"])
def test_styled_clean_roundtrip(text: str) -> None:
    cfg = Config()
    res = decode(_styled(text, cfg), cfg)
    assert res.ok and res.text == text


def test_styled_dual_channel_agrees() -> None:
    cfg = Config()
    res = decode(_styled("agreement", cfg), cfg)
    assert res.ok and res.text == "agreement"
    assert res.cross_check is True


@pytest.mark.parametrize("text", ["x", "rainy alley", "the maltese parrot"])
def test_styled_warped_roundtrip(text: str) -> None:
    cfg = Config()
    panel = _styled(text, cfg)
    for seed in range(4):
        rng = np.random.default_rng(seed)
        res = decode(warp_panel(panel, rng), cfg)
        assert res.ok, f"styled warp failed (seed={seed}): {res.failed_stage}"
        assert res.text == text


def test_styled_damaged_roundtrip() -> None:
    cfg = Config()
    text = "styled and scratched"
    panel = _styled(text, cfg)
    rng = np.random.default_rng(3)
    damaged = occlude_grid(panel, cfg, rng, coverage=0.1, fill=0)
    res = decode(jpeg(warp_panel(damaged, rng), quality=45), cfg)
    assert res.ok and res.text == text


@pytest.mark.parametrize("k", [0, 1, 2, 3])
def test_styled_rotation(k: int) -> None:
    cfg = Config()
    panel = _styled("spin", cfg)
    res = decode(np.rot90(panel, k), cfg)
    assert res.ok and res.text == "spin"

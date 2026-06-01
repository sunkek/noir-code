"""Decode under a strong lighting gradient (uneven light across a printed/photographed
panel). The margin-anchored flat-field fits the illumination from the known-white inner
margin and divides it out, rescuing reads that the plain global stretch can't."""

import numpy as np
import pytest

from noircode.decode.decoder import decode
from noircode.encode.encoder import encode
from noircode.simulate import warp_panel


def _print_capture(panel: np.ndarray, gradient: float, seed: int) -> np.ndarray:
    """Warp + paper range-compression + a left↔right brightness ramp."""
    p = warp_panel(panel, np.random.default_rng(seed), blur=3, noise_sigma=4.0)
    f = 35.0 + (p.astype(np.float32) / 255.0) * (205.0 - 35.0)
    h, w = f.shape
    _, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    f = f * (1.0 + gradient * ((xx / w) - 0.5))
    out: np.ndarray = np.clip(f, 0.0, 255.0).astype(np.uint8)
    return out


@pytest.mark.parametrize("seed", range(5))
def test_decode_under_lighting_gradient(seed: int) -> None:
    text = "https://noir.example/print"
    panel = encode(text, style=True, adaptive=True)
    cap = _print_capture(panel, gradient=0.45, seed=seed)  # ±22% across the panel
    assert decode(cap).text == text

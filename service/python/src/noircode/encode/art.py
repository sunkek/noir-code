"""Target artwork for the halftone grid.

The grid can carry a picture: each cell's outer area is shaded to match a target
image (quantized to the tonal levels), while only the cell's small center carries the
data bit (which is all the decoder samples). From a distance the grid reads as a
low-resolution noir image; up close it is a code.

``target_levels`` produces a (rows x cols) array of tonal levels in ``[0, levels)``.
Supply your own image, or use the built-in procedural noir cityscape.
"""

from __future__ import annotations

import cv2
import numpy as np

from noircode.config import Config


def _quantize(tone: np.ndarray, levels: int) -> np.ndarray:
    """Quantize a float [0,255] tone map to integer tonal levels."""
    q = np.round(tone / 255.0 * (levels - 1))
    return np.clip(q, 0, levels - 1).astype(np.int32)


def image_to_levels(image: np.ndarray, cfg: Config) -> np.ndarray:
    """Resize a grayscale/BGR image to the grid and quantize to tonal levels."""
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(
        gray.astype(np.float32), (cfg.grid_cols, cfg.grid_rows), interpolation=cv2.INTER_AREA
    )
    # Stretch contrast so the full tonal range is used.
    lo, hi = float(resized.min()), float(resized.max())
    if hi > lo:
        resized = (resized - lo) / (hi - lo) * 255.0
    return _quantize(resized, cfg.tonal_levels)


def default_scene(cfg: Config, seed: int | None = None) -> np.ndarray:
    """A procedural noir cityscape at night: moonlit sky, layered skyline, lit windows.

    ``seed`` randomizes the scene (moon position, building widths/heights/windows) while
    staying deterministic for a given seed. The encoder feeds a payload-derived seed so
    every message gets its own skyline. Falls back to ``cfg.seed`` when ``seed`` is None.
    """
    rows, cols = cfg.grid_rows, cfg.grid_cols
    rng = np.random.default_rng(cfg.seed if seed is None else seed)
    tone = np.empty((rows, cols), dtype=np.float32)

    # Sky: moonlit but kept below pure white (<= level-2 gray) so the moon is the only
    # truly white object -- no white stripe across the top.
    for r in range(rows):
        tone[r, :] = 200.0 - 95.0 * (r / rows)  # ~200 at top down to ~105 at horizon

    # Moon: a clean bright disc with a faint (non-white) halo, position jittered by seed.
    yy, xx = np.mgrid[0:rows, 0:cols].astype(np.float32)
    moon_cy = rows * float(rng.uniform(0.16, 0.28))
    moon_cx = cols * float(rng.uniform(0.52, 0.82))
    moon_r = rows * 0.11
    dist = np.sqrt((yy - moon_cy) ** 2 + (xx - moon_cx) ** 2)
    tone = np.where(dist < moon_r * 1.8, np.maximum(tone, 195.0), tone)  # soft halo (gray)
    tone[dist < moon_r] = 255.0  # bright core (only pure white in the scene)

    # Distant skyline: pale buildings sitting just above the horizon. Their mid-tone
    # renders as the criss-cross hatch in grid.py, reading as hazy background towers.
    far_horizon = int(rows * 0.46)
    c = 0
    while c < cols:
        bw = int(rng.integers(3, 8))
        top = far_horizon + int(rng.integers(-3, 4))
        top = max(top, int(rows * 0.34))
        tone[top:rows, c : min(cols, c + bw)] = 120.0  # mid level -> cross-hatch
        c += bw

    # Foreground skyline: tall solid-dark buildings. No painted windows -- the central
    # data dots already read as lit windows against the ink, so adding more competes
    # with them visually.
    horizon = int(rows * 0.56)
    c = 0
    while c < cols:
        bw = int(rng.integers(3, 6))
        top = int(rng.integers(horizon, rows - 4))
        tone[top:rows, c : min(cols, c + bw)] = 16.0  # near-solid ink
        c += bw

    return _quantize(tone, cfg.tonal_levels)

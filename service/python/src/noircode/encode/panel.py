"""Noir styling pass (Stage 5).

Lights the panel interior like a noir scene: a chiaroscuro vignette falls across the
whole grid (low amplitude, kept inside ``config.tonal_margin`` so each cell's sampled
mean still quantizes to its level), while the empty inner margin is driven much darker
for drama. Rain streaks and film grain finish it. The frame and the white quiet zone
are stamped *after* styling, so detection contrast is never touched. Styling that
breaks a decode gate is a bug.
"""

from __future__ import annotations

import cv2
import numpy as np

from noircode.config import Config
from noircode.geometry import PanelLayout

# Smooth vignette amplitude: gentle over the functional content (kept inside the tonal
# guard band so cell means stay on their level). The empty inner margin is left clean
# (white) so there is no muddy gray ring between the frame and the data.
_VIGN_GRID = 8.0
_VIGN_STRIP = 6.0
_VIGN_MARGIN = 0.0
_CONTENT_HALO = 6
_RAIN_DARKEN = 6.0
_GRAIN_SIGMA = 2.0


def _content_bbox(panel: PanelLayout) -> tuple[int, int, int, int]:
    gx0, gy0, gx1, gy1 = panel.grid_box
    sx0 = panel.strip_boxes[0][0]
    sy1 = panel.strip_boxes[-1][3]
    return (min(gx0, sx0), gy0, max(gx1, panel.strip_boxes[-1][2]), max(gy1, sy1))


def apply_style(
    canvas: np.ndarray, cfg: Config, panel: PanelLayout, seed: int | None = None
) -> np.ndarray:
    """Return a noir-styled copy of ``canvas`` (interior only) that still decodes."""
    rng = np.random.default_rng(cfg.seed if seed is None else seed)
    out = canvas.astype(np.float32)
    h, w = out.shape
    inner = cfg.frame_quiet_px + cfg.frame_thickness_px  # frame inner edge

    interior = np.zeros((h, w), dtype=np.float32)
    interior[inner : h - inner, inner : w - inner] = 1.0
    cx0, cy0, cx1, cy1 = _content_bbox(panel)
    gx0, gy0, gx1, gy1 = panel.grid_box
    k = max(3, (min(h, w) // 16) | 1)

    def _amp(grid_val: float, strip_val: float, margin_val: float) -> np.ndarray:
        a = np.zeros((h, w), dtype=np.float32)
        a[inner : h - inner, inner : w - inner] = margin_val
        a[
            max(0, cy0 - _CONTENT_HALO) : cy1 + _CONTENT_HALO,
            max(0, cx0 - _CONTENT_HALO) : cx1 + _CONTENT_HALO,
        ] = strip_val
        a[gy0:gy1, gx0:gx1] = grid_val
        a = cv2.GaussianBlur(a, (k, k), 0).astype(np.float32)
        return a * interior

    # Smooth radial vignette (low frequency -> removed by the decoder's illumination
    # flattening, so it can be strong over the grid).
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xx - w / 2) / (w / 2)
    ny = (yy - h / 2) / (h / 2)
    vignette = np.clip(np.sqrt(nx * nx + ny * ny) / np.sqrt(2.0), 0.0, 1.0) ** 1.5

    out -= _amp(_VIGN_GRID, _VIGN_STRIP, _VIGN_MARGIN) * vignette

    # Rain: long, sparse, near-diagonal streaks, lightly darkening.
    rain = np.zeros((h, w), dtype=np.float32)
    for _ in range(int(w * 0.5)):
        x = int(rng.integers(0, w))
        y = int(rng.integers(0, h))
        length = int(rng.integers(14, 40))
        for t in range(length):
            ry, rx = y + t, x + t // 4
            if 0 <= ry < h and 0 <= rx < w:
                rain[ry, rx] = 1.0
    out -= rain * _RAIN_DARKEN

    # Film grain.
    out += rng.normal(0.0, _GRAIN_SIGMA, out.shape).astype(np.float32)
    return np.clip(out, 0.0, 255.0).astype(np.uint8)

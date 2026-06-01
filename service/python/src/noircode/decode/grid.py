"""Channel A decode: sample a (rectified) grid raster back to symbols.

Assumes known geometry — Stage 2's detector rectifies a captured panel to this
canonical frame before handing it here. Each cell is sampled (mean gray), quantized
to the nearest tonal level, and flagged as an *erasure* when it lands inside the
guard band around a level boundary (``config.tonal_margin``).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from noircode.channels import Symbol
from noircode.config import Config


@dataclass(frozen=True)
class GridSample:
    """Result of sampling Channel A: one symbol per cell (None = erasure)."""

    symbols: list[Symbol]
    erasure_positions: list[int]

    @property
    def erasure_count(self) -> int:
        return len(self.erasure_positions)


def quantize_gray(gray: float, levels: int, margin: float) -> Symbol:
    """Quantize an 8-bit gray value to a tonal level, or None inside a guard band."""
    step = 255.0 / (levels - 1)
    level = int(round(gray / step))
    level = max(0, min(levels - 1, level))
    # Distance from the level centre; beyond (0.5 - margin)*step we are too close
    # to the boundary with a neighbour to trust the read.
    dist = abs(gray - level * step)
    if dist > (0.5 - margin) * step:
        return None
    return level


def sample_grid(img: np.ndarray, cfg: Config) -> GridSample:
    """Sample every cell of a canonical grid raster.

    ``img`` is expected at the encoder's canonical size
    (``grid_rows*cell_px`` by ``grid_cols*cell_px``); it is resampled by cell index
    so minor size drift after rectification is tolerated.
    """
    h, w = img.shape[:2]
    cell_h = h / cfg.grid_rows
    cell_w = w / cfg.grid_cols

    # A light blur averages the hatch lines without pulling the surrounding halftone
    # artwork into the sampled center (a big kernel would).
    img = cv2.blur(img, (3, 3))

    inset_h = cell_h * cfg.sample_inset
    inset_w = cell_w * cfg.sample_inset

    symbols: list[Symbol] = []
    erasures: list[int] = []
    for idx in range(cfg.grid_cells):
        r, c = divmod(idx, cfg.grid_cols)
        y0 = int(round(r * cell_h + inset_h))
        y1 = int(round((r + 1) * cell_h - inset_h))
        x0 = int(round(c * cell_w + inset_w))
        x1 = int(round((c + 1) * cell_w - inset_w))
        patch = img[max(y0, 0) : max(y1, y0 + 1), max(x0, 0) : max(x1, x0 + 1)]
        sym = quantize_gray(float(np.mean(patch)), cfg.tonal_levels, cfg.tonal_margin)
        symbols.append(sym)
        if sym is None:
            erasures.append(idx)
    return GridSample(symbols=symbols, erasure_positions=erasures)

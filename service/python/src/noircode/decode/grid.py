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


def compute_cell_means(img: np.ndarray, cfg: Config) -> np.ndarray:
    """Per-cell mean gray over the inner sample window, as float32.

    Shared between the fixed-threshold and adaptive (k-means) quantizers. The light
    3x3 blur averages out the hatch lines without pulling the surrounding halftone
    artwork into the sample window.
    """
    h, w = img.shape[:2]
    cell_h = h / cfg.grid_rows
    cell_w = w / cfg.grid_cols
    img = cv2.blur(img, (3, 3))
    inset_h = cell_h * cfg.sample_inset
    inset_w = cell_w * cfg.sample_inset
    means = np.zeros(cfg.grid_cells, dtype=np.float32)
    for idx in range(cfg.grid_cells):
        r, c = divmod(idx, cfg.grid_cols)
        y0 = int(round(r * cell_h + inset_h))
        y1 = int(round((r + 1) * cell_h - inset_h))
        x0 = int(round(c * cell_w + inset_w))
        x1 = int(round((c + 1) * cell_w - inset_w))
        patch = img[max(y0, 0) : max(y1, y0 + 1), max(x0, 0) : max(x1, x0 + 1)]
        means[idx] = float(np.mean(patch))
    return means


def sample_grid(img: np.ndarray, cfg: Config) -> GridSample:
    """Sample every cell with the encoder's fixed evenly-spaced tonal levels.

    The encoder pins each cell's *mean* gray to its level target (the hatched-data
    compensation depends on that), so the decoder reads the mean and quantizes it
    against the fixed ramp. Best when the capture preserves the tonal scale —
    digital roundtrips, mild photos. Real screen captures distort the scale
    nonlinearly; use :func:`sample_grid_adaptive` as a fallback for those.
    """
    means = compute_cell_means(img, cfg)
    symbols: list[Symbol] = []
    erasures: list[int] = []
    for idx in range(cfg.grid_cells):
        sym = quantize_gray(float(means[idx]), cfg.tonal_levels, cfg.tonal_margin)
        symbols.append(sym)
        if sym is None:
            erasures.append(idx)
    return GridSample(symbols=symbols, erasure_positions=erasures)


def sample_grid_adaptive(img: np.ndarray, cfg: Config) -> GridSample:
    """Sample every cell by clustering cell means into ``tonal_levels`` groups.

    Screen captures hit the cells through display gamma + camera tone-mapping, so the
    captured cell means cluster at *shifted* positions instead of the encoder's even
    ramp (0/85/170/255 at 4 levels). The clusters keep their *order* though, so a
    k-means partition over the observed means recovers each cell's level. Erasures
    are flagged when a cell sits roughly midway between its two nearest cluster
    centres — the same kind of guard-band logic as the fixed quantiser, just relative
    to the empirical centres.
    """
    means = compute_cell_means(img, cfg).reshape(-1, 1)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.5)
    _, labels, centers = cv2.kmeans(
        means, cfg.tonal_levels, None, crit, 10, cv2.KMEANS_PP_CENTERS
    )
    centers_flat = centers.flatten()
    order = np.argsort(centers_flat)
    sorted_centers = centers_flat[order]
    # Midpoint between each adjacent pair of cluster centres = the level boundaries.
    boundaries = (sorted_centers[:-1] + sorted_centers[1:]) / 2.0
    # Smallest inter-cluster gap sets the guard band: a cell within ``tonal_margin``
    # of any boundary is reported as an erasure (same logic as ``quantize_gray``,
    # just against empirical centres instead of fixed targets).
    min_gap = float(np.min(np.diff(sorted_centers))) if len(sorted_centers) > 1 else 0.0
    guard = cfg.tonal_margin * min_gap

    symbols: list[Symbol] = []
    erasures: list[int] = []
    for idx in range(cfg.grid_cells):
        v = float(means[idx, 0])
        # Symbol = ranked level matching ``v``'s position among sorted centres.
        sym: Symbol = int(np.searchsorted(boundaries, v))
        if boundaries.size > 0 and float(np.min(np.abs(v - boundaries))) < guard:
            sym = None
            erasures.append(idx)
        symbols.append(sym)
    return GridSample(symbols=symbols, erasure_positions=erasures)

"""Channel A: render a byte stream as a grid of hatched tonal-density cells.

Each cell carries ``config.bits_per_cell`` bits as one of ``config.tonal_levels``
tonal levels. Instead of a flat gray block, a cell is drawn as ink **hatching** whose
density encodes the level — the noir "shadow density" channel. The cell's mean gray
is held exactly at the level's target value (the light background is brightened to
compensate for the ink coverage), so the decoder's mean-sampling reads back the same
level it would from a flat block. Wide tonal margins absorb capture noise.
"""

from __future__ import annotations

import numpy as np

from noircode.channels import bytes_to_symbols
from noircode.config import Config

_INK = 0
_hatch_cache: dict[tuple[int, int, int, int], np.ndarray] = {}


def grid_capacity_bytes(cfg: Config) -> int:
    """How many whole bytes Channel A holds at this config."""
    total_bits = cfg.grid_cells * cfg.bits_per_cell
    return total_bits // 8


def level_to_gray(level: int, levels: int) -> int:
    """Map a tonal level in ``[0, levels)`` to an 8-bit gray value on an even ramp."""
    step = 255.0 / (levels - 1)
    return int(round(level * step))


def _hatch_mask(level: int, levels: int, cell: int) -> np.ndarray:
    """Binary ink mask for a cell: denser diagonal hatching for darker (lower) levels.

    Ink coverage is held *below* the level's darkness so the compensating light
    background stays <= 255. Darker tones add a cross-hatch for the classic noir look.
    """
    density = (levels - 1 - level) / (levels - 1)  # level 0 -> 1.0 (solid), top -> 0.0
    if density <= 0.0:
        return np.zeros((cell, cell), dtype=np.uint8)
    if density >= 0.999:
        return np.ones((cell, cell), dtype=np.uint8)

    coverage = min(0.9, density * 0.85)  # keep strictly under the darkness ceiling
    period = max(3.0, cell / 3.0)
    yy, xx = np.mgrid[0:cell, 0:cell].astype(np.float32)
    diag = 0.5 + 0.5 * np.sin((xx + yy) * 2 * np.pi / period)
    if density > 0.5:  # cross-hatch the darker tones
        anti = 0.5 + 0.5 * np.sin((xx - yy) * 2 * np.pi / period)
        field = np.minimum(diag, anti)
    else:
        field = diag
    # Threshold at the coverage quantile so the inked fraction is exactly `coverage`.
    threshold = float(np.quantile(field, coverage))
    mask: np.ndarray = (field <= threshold).astype(np.uint8)
    return mask


def _hatched_cell(level: int, levels: int, cell: int, inset: float) -> np.ndarray:
    """A cell rendered as hatching whose *inset-window* mean equals the target gray.

    The decoder samples the central inset window, so the light background is brightened
    to compensate for the ink coverage measured over that same window.
    """
    key = (level, levels, cell, int(round(inset * 1000)))
    cached = _hatch_cache.get(key)
    if cached is not None:
        return cached

    mask = _hatch_mask(level, levels, cell)
    lo = int(round(cell * inset))
    hi = max(lo + 1, int(round(cell * (1.0 - inset))))
    coverage = float(mask[lo:hi, lo:hi].mean())
    target = level_to_gray(level, levels)
    if coverage >= 1.0:
        img = np.zeros((cell, cell), dtype=np.uint8)
    else:
        background = int(round(min(255.0, target / (1.0 - coverage))))
        img = np.where(mask > 0, _INK, background).astype(np.uint8)
    _hatch_cache[key] = img
    return img


def _hatched_patch(level: int, levels: int, size: int) -> np.ndarray:
    """A ``size``x``size`` data patch rendered as hatching whose *whole-patch* mean
    equals the level's target gray, so mean-sampling still reads back the level.

    Unlike ``_hatched_cell`` (mean held over an inner window), the data patch is itself
    the sampled region, so the mean is pinned over the entire patch.
    """
    key = (-1, level, levels, size)
    cached = _hatch_cache.get(key)
    if cached is not None:
        return cached

    mask = _hatch_mask(level, levels, size)
    coverage = float(mask.mean())
    target = level_to_gray(level, levels)
    if coverage >= 1.0:
        img = np.zeros((size, size), dtype=np.uint8)
    else:
        background = int(round(min(255.0, target / (1.0 - coverage))))
        img = np.where(mask > 0, _INK, background).astype(np.uint8)
    _hatch_cache[key] = img
    return img


def render_grid(data: bytes, cfg: Config, target: np.ndarray | None = None) -> np.ndarray:
    """Render ``data`` (padded to grid capacity) to a grayscale uint8 raster.

    If ``target`` (a rows x cols level map) is given, each cell is rendered as a
    halftone: its outer area takes the target's tone (the artwork) while only the
    central sampled window carries the data level. The decoder samples that window,
    so the picture is cosmetic. Raises ``ValueError`` if ``data`` exceeds capacity.
    """
    capacity = grid_capacity_bytes(cfg)
    if len(data) > capacity:
        raise ValueError(f"data {len(data)}B exceeds Channel A capacity {capacity}B")
    padded = data.ljust(capacity, b"\x00")

    symbols = bytes_to_symbols(padded, cfg.bits_per_cell)
    assert len(symbols) == cfg.grid_cells, (len(symbols), cfg.grid_cells)

    cell = cfg.cell_px
    levels = cfg.tonal_levels
    # The data patch fills cell_sample_inset; it must contain the (inner) sample window.
    lo = int(round(cell * cfg.cell_sample_inset))
    hi = max(lo + 1, int(round(cell * (1.0 - cfg.cell_sample_inset))))

    h = cfg.grid_rows * cell
    w = cfg.grid_cols * cell
    img = np.empty((h, w), dtype=np.uint8)
    for idx, sym in enumerate(symbols):
        r, c = divmod(idx, cfg.grid_cols)
        # The sampled data carrier is a FLAT tone (exact mean = level, robust). Only the
        # un-sampled outer area is hatched, and only to render the halftone artwork.
        data_gray = level_to_gray(sym, levels)
        if target is None:
            if cfg.hatched_data:
                # No artwork target, but hatch the data anyway: fill the whole cell with
                # hatching of the data level (cosmetic) and pin the sampled center window's
                # mean to the level so the decoder still reads it exactly.
                block = _hatched_patch(sym, levels, cell).copy()
                block[lo:hi, lo:hi] = _hatched_patch(sym, levels, hi - lo)
            else:
                block = np.full((cell, cell), data_gray, dtype=np.uint8)
        else:
            block = _hatched_cell(int(target[r, c]), levels, cell, cfg.sample_inset).copy()
            if cfg.hatched_data:
                # Render the data patch as hatching too (mean = level), so the whole
                # panel reads as line art instead of flat gray dots.
                block[lo:hi, lo:hi] = _hatched_patch(sym, levels, hi - lo)
            else:
                block[lo:hi, lo:hi] = data_gray
        img[r * cell : (r + 1) * cell, c * cell : (c + 1) * cell] = block
    return img

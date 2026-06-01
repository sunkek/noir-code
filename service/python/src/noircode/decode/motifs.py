"""Channel B decode: sample the bottom tonal-module strip back to symbols.

Each module box is cropped from the rectified canonical panel and its mean tone is
quantized to a level (reusing Channel A's guard-band logic). A module landing inside
a guard band — or wiped flat by occlusion onto a boundary — is reported as an erasure.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from noircode.channels import Symbol
from noircode.config import Config
from noircode.decode.grid import quantize_gray
from noircode.geometry import PanelLayout


@dataclass(frozen=True)
class MotifSample:
    symbols: list[Symbol]
    erasure_positions: list[int]

    @property
    def erasure_count(self) -> int:
        return len(self.erasure_positions)


def sample_channel_b(canonical: np.ndarray, cfg: Config, panel: PanelLayout) -> MotifSample:
    """Sample every Channel B strip module from a rectified canonical panel image."""
    symbols: list[Symbol] = []
    erasures: list[int] = []
    inset = cfg.cell_sample_inset
    for slot, (x0, y0, x1, y1) in enumerate(panel.strip_boxes):
        dx = int(round((x1 - x0) * inset))
        dy = int(round((y1 - y0) * inset))
        patch = canonical[max(y0 + dy, 0) : y1 - dy, max(x0 + dx, 0) : x1 - dx]
        if patch.size == 0:
            sym: Symbol = None
        else:
            sym = quantize_gray(float(np.mean(patch)), cfg.motif_alphabet_size, cfg.tonal_margin)
        symbols.append(sym)
        if sym is None:
            erasures.append(slot)
    return MotifSample(symbols=symbols, erasure_positions=erasures)

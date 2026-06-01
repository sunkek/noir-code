"""Channel B render: the bottom tonal-module strip (the "frame line").

Channel B carries MAGIC + LEN + a checksum of Channel A as a short, high-reliability
byte string. Each module is a flat tonal block (no hatching) so it samples back
crisply — Channel B trades bandwidth for reliability. The row of shaded modules reads
as a decorative rule between the grid and the bottom frame.
"""

from __future__ import annotations

import numpy as np

from noircode.channels import bytes_to_symbols
from noircode.config import Config
from noircode.encode.grid import level_to_gray
from noircode.geometry import PanelLayout


def draw_channel_b(canvas: np.ndarray, cfg: Config, panel: PanelLayout, data: bytes) -> None:
    """Draw ``data`` (exactly Channel B capacity) as the tonal strip, in place."""
    if len(data) != cfg.channel_b_bytes:
        raise ValueError(f"Channel B needs {cfg.channel_b_bytes}B, got {len(data)}B")
    symbols = bytes_to_symbols(data, cfg.bits_per_motif)
    assert len(symbols) == cfg.motif_count, (len(symbols), cfg.motif_count)

    for sym, (x0, y0, x1, y1) in zip(symbols, panel.strip_boxes, strict=True):
        canvas[y0:y1, x0:x1] = level_to_gray(sym, cfg.motif_alphabet_size)

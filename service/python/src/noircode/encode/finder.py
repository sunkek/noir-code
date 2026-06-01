"""Finder scaffold: a solid black border frame around the panel.

Replaces the old corner squares. The frame is a payload-independent black rectangle
ring sitting inside a white quiet zone; the decoder recovers its four outer corners
for perspective rectification. It doubles as the noir comic panel border.
"""

from __future__ import annotations

import numpy as np

from noircode.config import Config
from noircode.geometry import PanelLayout

FRAME_DARK = 0


def draw_frame(canvas: np.ndarray, cfg: Config, panel: PanelLayout) -> None:
    """Draw the black border frame onto ``canvas`` in place."""
    q = cfg.frame_quiet_px
    f = cfg.frame_thickness_px
    h, w = canvas.shape
    x0, y0, x1, y1 = q, q, w - q, h - q  # frame outer rectangle

    canvas[y0 : y0 + f, x0:x1] = FRAME_DARK  # top
    canvas[y1 - f : y1, x0:x1] = FRAME_DARK  # bottom
    canvas[y0:y1, x0 : x0 + f] = FRAME_DARK  # left
    canvas[y0:y1, x1 - f : x1] = FRAME_DARK  # right


def draw_inner_rule(canvas: np.ndarray, cfg: Config, panel: PanelLayout) -> None:
    """Draw a thin black double-rule just inside the frame (cosmetic comic border).

    Smaller than the main frame, so it never becomes the largest detected contour.
    """
    q, f = cfg.frame_quiet_px, cfg.frame_thickness_px
    h, w = canvas.shape
    gap = max(3, f // 2)
    rule = max(1, f // 6)
    x0, y0, x1, y1 = q + f + gap, q + f + gap, w - q - f - gap, h - q - f - gap
    if x1 - x0 < 2 * rule or y1 - y0 < 2 * rule:
        return
    canvas[y0 : y0 + rule, x0:x1] = FRAME_DARK
    canvas[y1 - rule : y1, x0:x1] = FRAME_DARK
    canvas[y0:y1, x0 : x0 + rule] = FRAME_DARK
    canvas[y0:y1, x1 - rule : x1] = FRAME_DARK

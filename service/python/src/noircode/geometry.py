"""Canonical panel geometry shared by the encoder and the decoder.

A canonical (pre-styling, un-warped) panel is laid out as::

    +---------------------------------------+   <- white quiet zone
    |  #################################### |   <- black border frame
    |  #                                  # |
    |  #    Channel A hatching grid       # |
    |  #                                  # |
    |  #  [Channel B tonal-module strip]  # |   <- the bottom "frame line"
    |  #################################### |
    +---------------------------------------+

The black border **frame** is the detection scaffold: the decoder finds its four
outer corners and maps them onto the canonical corners for perspective rectification.
The frame is rotationally ambiguous, so orientation is resolved by trying all four
90-degree rotations and accepting the one whose CRC validates.
"""

from __future__ import annotations

from dataclasses import dataclass

from noircode.config import Config

Point = tuple[float, float]
Box = tuple[int, int, int, int]


@dataclass(frozen=True)
class PanelLayout:
    width: int
    height: int
    frame_thickness: int
    frame_corners: tuple[Point, Point, Point, Point]  # outer TL, TR, BR, BL
    grid_x: int
    grid_y: int
    grid_w: int
    grid_h: int
    strip_boxes: tuple[Box, ...]  # Channel B modules, left -> right

    @property
    def grid_box(self) -> Box:
        return (self.grid_x, self.grid_y, self.grid_x + self.grid_w, self.grid_y + self.grid_h)


def layout(cfg: Config) -> PanelLayout:
    """Compute the canonical panel layout for ``cfg``."""
    gw = cfg.grid_cols * cfg.cell_px
    gh = cfg.grid_rows * cfg.cell_px

    q = cfg.frame_quiet_px
    f = cfg.frame_thickness_px
    m = cfg.content_margin_px
    strip_h = cfg.motif_box_px
    gap = cfg.strip_gap_px

    origin = q + f + m  # minimum inset inside quiet + frame + margin
    content_w = gw
    content_h = gh + gap + strip_h
    # Square panel so the four 90-degree orientations are interchangeable for the
    # rotation trial; content is centered, extra whitespace becomes inner margin.
    side = max(content_w, content_h) + 2 * origin
    width = height = side

    frame_corners = (
        (float(q), float(q)),
        (float(width - q), float(q)),
        (float(width - q), float(height - q)),
        (float(q), float(height - q)),
    )

    grid_x = (side - gw) // 2
    grid_y = (side - content_h) // 2
    strip_y0 = grid_y + gh + gap
    seg = gw / cfg.motif_count
    strip_boxes: list[Box] = []
    for i in range(cfg.motif_count):
        x0 = int(round(grid_x + i * seg))
        x1 = int(round(grid_x + (i + 1) * seg))
        strip_boxes.append((x0, strip_y0, x1, strip_y0 + strip_h))

    return PanelLayout(
        width=width,
        height=height,
        frame_thickness=f,
        frame_corners=frame_corners,
        grid_x=grid_x,
        grid_y=grid_y,
        grid_w=gw,
        grid_h=gh,
        strip_boxes=tuple(strip_boxes),
    )

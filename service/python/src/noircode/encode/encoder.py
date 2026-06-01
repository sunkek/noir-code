"""Encode orchestration: text -> canonical noir-code panel raster.

Stage 2 wiring (no ECC, no motifs, no styling yet): build the frame, render Channel
A's grid, drop it into the canonical panel, and stamp the corner finders. Later
stages fold in Reed-Solomon (Stage 3), Channel B motifs (Stage 4), and the noir
styling pass (Stage 5) without changing this contract.
"""

from __future__ import annotations

import zlib

import numpy as np

from noircode.channels import checksum_byte, interleave
from noircode.config import Config, select_grid
from noircode.ecc import encode_codeword
from noircode.encode.art import default_scene, image_to_levels
from noircode.encode.finder import draw_frame, draw_inner_rule
from noircode.encode.grid import render_grid
from noircode.encode.motifs import draw_channel_b
from noircode.encode.panel import apply_style
from noircode.geometry import PanelLayout, layout
from noircode.payload import build_frame

PANEL_BACKGROUND = 255


def channel_b_bytes(codeword: bytes, cfg: Config) -> bytes:
    """Critical header mirrored onto Channel B: MAGIC + LEN + checksum of Channel A.

    RS is systematic, so the codeword's leading bytes are the frame's MAGIC and LEN.
    The final byte is a checksum of the whole Channel A codeword for cross-checking.
    """
    header = codeword[: cfg.channel_b_bytes - 1]
    return header + bytes([checksum_byte(codeword)])


def encode(
    text: str,
    cfg: Config | None = None,
    *,
    style: bool = False,
    art: np.ndarray | None = None,
    adaptive: bool = False,
) -> np.ndarray:
    """Encode ``text`` to a canonical grayscale panel (uint8).

    ``style=True`` applies the noir styling pass and renders the grid as a halftone of
    a built-in noir cityscape. Pass ``art`` (a grayscale/BGR image) to use your own
    picture as the grid's artwork. The default (no style, no art) keeps the clean
    functional panel so encoder output stays byte-stable for fixtures.

    ``adaptive=True`` shrinks the grid to the smallest :data:`GRID_VERSIONS` size that
    fits the payload (smaller panel for short text). The decoder trials the versions, so
    no extra signalling is needed.
    """
    cfg = cfg or Config()
    payload = text.encode("utf-8")
    if adaptive:
        cfg = select_grid(len(payload), cfg)
    frame = build_frame(payload)
    codeword = encode_codeword(frame, cfg)
    panel: PanelLayout = layout(cfg)

    if art is not None:
        target = image_to_levels(art, cfg)
    elif style:
        # Seed the procedural scene from the payload so each message gets its own
        # skyline, while staying deterministic for a given (text, config).
        target = default_scene(cfg, seed=zlib.crc32(codeword) ^ cfg.seed)
    else:
        target = None

    canvas = np.full((panel.height, panel.width), PANEL_BACKGROUND, dtype=np.uint8)
    grid = render_grid(interleave(codeword), cfg, target)
    x0, y0, x1, y1 = panel.grid_box
    canvas[y0:y1, x0:x1] = grid
    draw_channel_b(canvas, cfg, panel, channel_b_bytes(codeword, cfg))

    # Light the interior as a scene first, then stamp the crisp frame on top so it
    # stays pure black on a white quiet zone for detection.
    if style:
        canvas = apply_style(canvas, cfg, panel)
    draw_frame(canvas, cfg, panel)
    if style:
        draw_inner_rule(canvas, cfg, panel)
    return canvas

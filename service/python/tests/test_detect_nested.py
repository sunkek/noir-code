"""Decode must survive an outer border nested around the panel (e.g. a screenshot
that includes window chrome / its own frame). The detector returns several candidate
frames and the decoder picks the one that validates."""

import cv2
import numpy as np

from noircode.config import Config
from noircode.decode.decoder import decode
from noircode.encode.encoder import encode


def _wrap(panel: np.ndarray, margin: int, border: int) -> np.ndarray:
    """Pad the panel with a white quiet margin then a solid black outer border —
    mimicking a screenshot whose own frame is larger than the panel's frame."""
    h, w = panel.shape
    out = np.full((h + 2 * (margin + border), w + 2 * (margin + border)), 255, np.uint8)
    out[:border, :] = out[-border:, :] = out[:, :border] = out[:, -border:] = 0
    out[margin + border : margin + border + h, margin + border : margin + border + w] = panel
    return out


def test_decode_with_outer_border() -> None:
    text = "https://noir.example/wrapped"
    panel = encode(text, style=True, adaptive=True)
    wrapped = _wrap(panel, margin=18, border=6)
    assert decode(wrapped, Config()).text == text


def test_decode_with_outer_border_and_scale() -> None:
    text = "nested + resized"
    panel = encode(text, adaptive=True)
    wrapped = _wrap(panel, margin=24, border=8)
    scaled = cv2.resize(wrapped, None, fx=0.7, fy=0.7, interpolation=cv2.INTER_AREA)
    assert decode(scaled, Config()).text == text

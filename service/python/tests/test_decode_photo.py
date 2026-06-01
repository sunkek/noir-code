"""Decode a real phone photo of the panel on a monitor: perspective, moiré, and a
compressed/shifted tonal range. The level-normalization step (frame/quiet-zone anchored
global stretch) plus RS erasure correction must recover the payload."""

from pathlib import Path

import cv2
import pytest

from noircode.config import Config
from noircode.decode.decoder import decode

FIXTURE = Path(__file__).parent / "fixtures" / "photo_monitor.png"


@pytest.mark.skipif(not FIXTURE.exists(), reason="photo fixture not present")
def test_decode_monitor_photo() -> None:
    img = cv2.imread(str(FIXTURE), cv2.IMREAD_GRAYSCALE)
    assert img is not None
    res = decode(img, Config())
    assert res.text == "https://noir.example"

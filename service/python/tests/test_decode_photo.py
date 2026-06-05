"""Decode a real phone photo of the panel on a monitor: perspective, moiré, and a
compressed/shifted tonal range. The level-normalization step (frame/quiet-zone anchored
global stretch) plus RS erasure correction must recover the payload."""

from pathlib import Path

import cv2
import pytest

from noircode.config import Config
from noircode.decode.decoder import decode

FIXTURE = Path(__file__).parent / "fixtures" / "photo_monitor.png"
FIXTURE_HATCHED = Path(__file__).parent / "fixtures" / "photo_screen_hatched.png"


@pytest.mark.skipif(not FIXTURE.exists(), reason="photo fixture not present")
def test_decode_monitor_photo() -> None:
    img = cv2.imread(str(FIXTURE), cv2.IMREAD_GRAYSCALE)
    assert img is not None
    res = decode(img, Config())
    assert res.text == "https://noir.example"


@pytest.mark.skipif(not FIXTURE_HATCHED.exists(), reason="photo fixture not present")
def test_decode_screen_hatched_photo() -> None:
    """Phone photo of a hatched + noir-styled panel on a monitor. Display gamma plus
    camera tone-mapping push the captured tonal levels off the encoder's even ramp,
    so the fixed-threshold sampler reads mid-levels as erasures. The adaptive
    (k-means) sampler in the decoder pipeline rescues the read."""
    img = cv2.imread(str(FIXTURE_HATCHED), cv2.IMREAD_GRAYSCALE)
    assert img is not None
    res = decode(img, Config())
    assert res.text == "https://noir-code.suncake.xyz"

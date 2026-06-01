"""hatched_data renders engraving-style data cells and stays decodable.

The flag must work independently of the noir styling / artwork target: with no art
target the whole cell is hatched while the sampled centre still pins the level.
"""

import dataclasses

import numpy as np
import pytest

from noircode.config import Config
from noircode.decode.decoder import decode
from noircode.encode.encoder import encode
from noircode.simulate import warp_panel

HATCHED = dataclasses.replace(Config(), hatched_data=True)


@pytest.mark.parametrize("text", ["hi", "https://noir.example/x", "a" * 55, "a" * 173])
@pytest.mark.parametrize("style", [False, True])
def test_hatched_data_roundtrip(text: str, style: bool) -> None:
    panel = encode(text, HATCHED, style=style, adaptive=True)
    assert decode(panel, HATCHED).text == text


@pytest.mark.parametrize("style", [False, True])
def test_hatched_data_survives_warp(style: bool) -> None:
    panel = encode("a" * 120, HATCHED, style=style)
    warped = warp_panel(panel, np.random.default_rng(3), blur=3, noise_sigma=5.0)
    assert decode(warped, HATCHED).text == "a" * 120

"""Stage 1 gate: text -> grid raster -> text, exact match, no camera, no RS.

Proves Channel A's tonal-density encoding digitally before any styling or capture
noise. The encoder writes cells exactly on level centres, so a clean round-trip
must produce zero erasures and an exact byte match.
"""

import random

import pytest

from noircode.channels import symbols_to_bytes
from noircode.config import Config
from noircode.decode.grid import sample_grid
from noircode.encode.grid import grid_capacity_bytes, render_grid
from noircode.payload import build_frame, parse_frame


def _roundtrip(text: str, cfg: Config) -> str:
    frame = build_frame(text.encode("utf-8"))
    raster = render_grid(frame, cfg)
    sample = sample_grid(raster, cfg)
    assert sample.erasure_count == 0, "clean digital raster must have no erasures"
    recovered = symbols_to_bytes(sample.symbols, cfg.bits_per_cell)
    return parse_frame(recovered).decode("utf-8")


@pytest.mark.parametrize("text", ["", "x", "hello", "The quick brown fox.", "héllo nöir 🌃"])
def test_roundtrip_fixed(text: str) -> None:
    assert _roundtrip(text, Config()) == text


def test_roundtrip_random() -> None:
    cfg = Config()
    rng = random.Random(1234)
    max_payload = grid_capacity_bytes(cfg) - 7  # frame overhead
    for _ in range(50):
        n = rng.randint(0, max_payload)
        text = "".join(chr(rng.randint(32, 126)) for _ in range(n))
        assert _roundtrip(text, cfg) == text


@pytest.mark.parametrize("levels", [2, 4, 8])
def test_roundtrip_tonal_levels(levels: int) -> None:
    cfg = Config(tonal_levels=levels)
    assert _roundtrip("density levels", cfg) == "density levels"


def test_over_capacity_raises() -> None:
    cfg = Config()
    too_big = b"\x00" * (grid_capacity_bytes(cfg) + 1)
    with pytest.raises(ValueError, match="exceeds Channel A capacity"):
        render_grid(too_big, cfg)


def test_encoder_is_byte_stable() -> None:
    cfg = Config()
    frame = build_frame(b"determinism")
    assert render_grid(frame, cfg).tobytes() == render_grid(frame, cfg).tobytes()

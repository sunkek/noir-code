"""Stage 3 gate: Reed-Solomon recovers exact text under damage, fails gracefully past it.

Damage = warp + occlusion patches + JPEG. Up to the configured parity budget the
exact text is recovered; beyond it the decoder reports failure with diagnostics
instead of returning garbage.
"""

import numpy as np
import pytest

from _capture import jpeg, occlude_grid, warp_panel
from noircode.config import Config
from noircode.decode.decoder import decode
from noircode.ecc import EccError, decode_codeword, encode_codeword
from noircode.encode.encoder import encode
from noircode.payload import build_frame, parse_frame


def test_ecc_corrects_byte_erasures() -> None:
    cfg = Config()
    frame = build_frame(b"reed-solomon")
    codeword = bytearray(encode_codeword(frame, cfg))
    # Erase within each block's parity budget (erasures cost 1 each, applied per block).
    erase_pos: list[int] = []
    offset = 0
    for data_len, parity in cfg.rs_blocks:
        for i in range(offset, offset + parity):
            codeword[i] = 0
            erase_pos.append(i)
        offset += data_len + parity
    recovered = decode_codeword(bytes(codeword), erase_pos, cfg)
    assert parse_frame(recovered) == b"reed-solomon"


def test_ecc_fails_past_budget() -> None:
    cfg = Config()
    frame = build_frame(b"too much damage")
    codeword = bytearray(encode_codeword(frame, cfg))
    # Blow the first block's budget: parity+4 erasures in block 0.
    block0_total = sum(cfg.rs_blocks[0])
    erase_pos = list(range(min(cfg.rs_blocks[0][1] + 4, block0_total)))
    for i in erase_pos:
        codeword[i] = 0xFF
    with pytest.raises(EccError):
        decode_codeword(bytes(codeword), erase_pos, cfg)


@pytest.mark.parametrize("coverage", [0.05, 0.10, 0.15])
def test_recovers_under_occlusion(coverage: float) -> None:
    cfg = Config()
    text = "shadows fall on rain"
    panel = encode(text, cfg)
    for seed in range(4):
        rng = np.random.default_rng(seed)
        damaged = occlude_grid(panel, cfg, rng, coverage, fill=0)
        captured = warp_panel(damaged, rng)
        res = decode(captured, cfg)
        assert res.ok, f"failed at coverage={coverage} seed={seed}: {res.failed_stage}"
        assert res.text == text


def test_recovers_under_jpeg() -> None:
    cfg = Config()
    panel = encode("compressed noir", cfg)
    rng = np.random.default_rng(7)
    captured = jpeg(warp_panel(panel, rng), quality=40)
    res = decode(captured, cfg)
    assert res.ok and res.text == "compressed noir"


def test_graceful_failure_past_threshold() -> None:
    cfg = Config()
    panel = encode("unrecoverable", cfg)
    rng = np.random.default_rng(0)
    damaged = occlude_grid(panel, cfg, rng, coverage=0.85, fill=0)
    captured = warp_panel(damaged, rng)
    res = decode(captured, cfg)
    assert not res.ok
    assert res.text is None
    assert res.failed_stage is not None


def test_confidence_reported() -> None:
    cfg = Config()
    panel = encode("diagnostics", cfg)
    res = decode(panel, cfg)
    assert res.ok
    assert 0.0 <= res.confidence <= 1.0

"""Reed-Solomon error correction over the frame.

The whole frame is RS-encoded to a fixed-length codeword that exactly fills Channel
A's grid capacity: ``rs_data_bytes`` of (padded) frame followed by ``rs_parity_bytes``
of parity. Decoding accepts erased byte positions from the grid sampler, which RS
corrects roughly twice as efficiently as unknown errors.
"""

from __future__ import annotations

from reedsolo import ReedSolomonError, RSCodec

from noircode.config import Config


class EccError(ValueError):
    """Raised when a codeword cannot be corrected within the parity budget."""


# Deterministic, varied filler for the unused data region. Avoids a flat run of
# 0x00 (which would render as a solid black slab); the decoder ignores everything
# past the frame's declared length, so the exact pattern only matters for looks.
def _padding(length: int) -> bytes:
    return bytes((i * 37 + 11) & 0xFF for i in range(length))


def encode_codeword(frame: bytes, cfg: Config) -> bytes:
    """RS-encode ``frame`` into a codeword that fills Channel A capacity.

    The codeword is a concatenation of per-block ``data + parity`` segments so each
    block stays within the 255-symbol Reed-Solomon limit.
    """
    if len(frame) > cfg.rs_data_bytes:
        raise EccError(f"frame {len(frame)}B exceeds RS data capacity {cfg.rs_data_bytes}B")
    padded = frame + _padding(cfg.rs_data_bytes - len(frame))

    out = bytearray()
    pos = 0
    for data_len, parity in cfg.rs_blocks:
        chunk = padded[pos : pos + data_len]
        pos += data_len
        out += RSCodec(parity).encode(bytearray(chunk))
    assert len(out) == cfg.channel_a_capacity_bytes, len(out)
    return bytes(out)


def correct_codeword(codeword: bytes, erase_pos: list[int], cfg: Config) -> tuple[bytes, bytes]:
    """RS-correct a codeword block by block.

    Returns (data region, full corrected codeword). Raises :class:`EccError` if any
    block's errors+erasures exceed its parity budget.
    """
    data = bytearray()
    full = bytearray()
    offset = 0
    for data_len, parity in cfg.rs_blocks:
        total = data_len + parity
        segment = bytearray(codeword[offset : offset + total])
        local_erase = [p - offset for p in erase_pos if offset <= p < offset + total]
        try:
            decoded, decoded_full, _ = RSCodec(parity).decode(segment, erase_pos=local_erase)
        except ReedSolomonError as exc:
            raise EccError(str(exc)) from exc
        data += decoded
        full += decoded_full
        offset += total
    return bytes(data), bytes(full)


def decode_codeword(codeword: bytes, erase_pos: list[int], cfg: Config) -> bytes:
    """RS-correct a codeword and return the ``rs_data_bytes`` payload region."""
    data, _ = correct_codeword(codeword, erase_pos, cfg)
    return data

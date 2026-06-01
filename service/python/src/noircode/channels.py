"""Codeword <-> channel symbol assignment.

Stage 1 only needs the bit-packing primitive: turn a byte string into a list of
``bits_per_cell``-wide symbols and back. Channel A/B splitting (MAGIC/LEN/checksum
onto motifs, the rest onto the grid) arrives in Stage 4 and will build on these.

Symbols may be ``None`` to denote an *erasure* (a known-missing position). With no
ECC (Stage 1) an erasure is unrecoverable; Stage 3 hands erasure positions to RS.
"""

from __future__ import annotations

import zlib
from math import gcd, isqrt

Symbol = int | None


def checksum_byte(data: bytes) -> int:
    """Low byte of CRC32 over ``data`` — the cross-channel checksum stored in B."""
    return zlib.crc32(data) & 0xFF


def interleave_perm(n: int) -> list[int]:
    """A deterministic stride permutation of ``range(n)``.

    Spreads consecutive codeword bytes across the grid so a localized occlusion patch
    is shared roughly evenly across all RS blocks (burst -> distributed erasures),
    which per-block Reed-Solomon corrects far better than a burst concentrated in one
    block. The stride is coprime to ``n`` so the map is a bijection.
    """
    if n <= 1:
        return list(range(n))
    stride = max(2, isqrt(n))
    while gcd(stride, n) != 1:
        stride += 1
    return [(k * stride) % n for k in range(n)]


def interleave(codeword: bytes) -> bytes:
    """Reorder codeword bytes for spatial placement (inverse: :func:`deinterleave`)."""
    perm = interleave_perm(len(codeword))
    return bytes(codeword[perm[k]] for k in range(len(codeword)))


def deinterleave(placed: bytes, erase_slots: list[int]) -> tuple[bytes, list[int]]:
    """Invert :func:`interleave`, remapping erased slots to codeword positions."""
    n = len(placed)
    perm = interleave_perm(n)
    out = bytearray(n)
    for k in range(n):
        out[perm[k]] = placed[k]
    erase = [perm[k] for k in erase_slots]
    return bytes(out), erase


def bytes_to_symbols(data: bytes, bits_per_cell: int) -> list[int]:
    """Pack ``data`` MSB-first into a flat list of ``bits_per_cell``-wide symbols.

    The bit count must divide evenly; callers pad ``data`` to a capacity that makes
    ``len(data) * 8`` a multiple of ``bits_per_cell``.
    """
    if bits_per_cell < 1:
        raise ValueError("bits_per_cell must be >= 1")
    total_bits = len(data) * 8
    if total_bits % bits_per_cell != 0:
        raise ValueError(f"{total_bits} bits not divisible by {bits_per_cell}")

    mask = (1 << bits_per_cell) - 1
    symbols: list[int] = []
    acc = 0
    nbits = 0
    for byte in data:
        acc = (acc << 8) | byte
        nbits += 8
        while nbits >= bits_per_cell:
            nbits -= bits_per_cell
            symbols.append((acc >> nbits) & mask)
    return symbols


def symbols_to_codeword(symbols: list[Symbol], bits_per_cell: int) -> tuple[bytes, list[int]]:
    """Pack symbols (with erasures) into codeword bytes + erased byte positions.

    Cells need not align to byte boundaries (e.g. bits_per_cell=3). Any output byte
    that draws a bit from an erased cell is itself reported as a byte-level erasure,
    which is what Reed-Solomon consumes. Erased cells contribute 0 bits to the value.
    """
    total_bits = len(symbols) * bits_per_cell
    if total_bits % 8 != 0:
        raise ValueError(f"{total_bits} bits not byte-aligned")

    bit_val = bytearray(total_bits)
    bit_tainted = bytearray(total_bits)
    pos = 0
    for sym in symbols:
        erased = sym is None
        value = 0 if sym is None else sym
        for k in range(bits_per_cell):
            bit_val[pos] = (value >> (bits_per_cell - 1 - k)) & 1
            bit_tainted[pos] = 1 if erased else 0
            pos += 1

    out = bytearray()
    erasures: list[int] = []
    for b in range(total_bits // 8):
        byte = 0
        tainted = 0
        for k in range(8):
            byte = (byte << 1) | bit_val[b * 8 + k]
            tainted |= bit_tainted[b * 8 + k]
        out.append(byte)
        if tainted:
            erasures.append(b)
    return bytes(out), erasures


def symbols_to_bytes(symbols: list[Symbol], bits_per_cell: int) -> bytes:
    """Inverse of :func:`bytes_to_symbols`. Raises if any symbol is an erasure.

    The symbol count must pack into a whole number of bytes.
    """
    if bits_per_cell < 1:
        raise ValueError("bits_per_cell must be >= 1")
    total_bits = len(symbols) * bits_per_cell
    if total_bits % 8 != 0:
        raise ValueError(f"{total_bits} bits not byte-aligned")

    out = bytearray()
    acc = 0
    nbits = 0
    for sym in symbols:
        if sym is None:
            raise ValueError("cannot reconstruct bytes with erasures present (no ECC)")
        acc = (acc << bits_per_cell) | sym
        nbits += bits_per_cell
        while nbits >= 8:
            nbits -= 8
            out.append((acc >> nbits) & 0xFF)
    return bytes(out)

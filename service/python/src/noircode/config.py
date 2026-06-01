"""All tunable parameters in one place.

No magic numbers anywhere else in the code paths: grid size, tonal levels, RS
parity, margins and frame constants all live here with documented defaults. The
art <-> capacity <-> robustness trade is driven entirely by these knobs.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

# Frame layout constants. Fixed by the format, not tunable.
MAGIC_BYTES = 1
LEN_BYTES = 2
CRC_BYTES = 4
HEADER_BYTES = MAGIC_BYTES + LEN_BYTES  # MAGIC + LEN, before payload
FRAME_OVERHEAD_BYTES = HEADER_BYTES + CRC_BYTES  # everything that is not payload

# Current format/version id stored in MAGIC. Bump on any wire-format change.
MAGIC_VALUE = 0x4E  # 'N' for noir; pinned format id
MAX_PAYLOAD_LEN = (1 << (LEN_BYTES * 8)) - 1  # LEN is big-endian, this many bytes


@dataclass(frozen=True)
class Config:
    """Encoder/decoder tunables. Defaults start generous (robust) and tighten later.

    Determinism: encoder output for a given (text, config, seed) is byte-stable, so
    every field that affects rendering must be captured here.
    """

    # --- Channel A: hatching-density grid ---
    grid_cols: int = 40
    grid_rows: int = 40
    tonal_levels: int = 4
    """Number of quantized shadow-density levels per cell. Start small with wide margins."""
    tonal_margin: float = 0.15
    """Fraction of a level's width treated as a boundary guard band. Samples landing
    inside the guard band are reported to RS as erasures rather than guessed."""

    # --- Reed-Solomon error correction ---
    rs_parity_ratio: float = 0.55
    """Parity symbols as a fraction of the codeword. Hatched (artful) cells trade some
    robustness for the noir look, so the default buys it back here: ~55% parity holds
    decode through meaningful grid damage. More parity = more robust, fewer payload bytes."""

    # --- Channel B: tonal-module strip (the bottom "frame line") ---
    motif_count: int = 16
    """Number of Channel B strip modules. Carries the critical header (MAGIC + LEN) plus
    a checksum of Channel A: 4 bytes = 16 modules at 2 bits each."""
    motif_alphabet_size: int = 4
    """Tonal levels per strip module; log2 is the bits per module."""
    motif_box_px: int = 18
    """Height of the Channel B strip band, in canonical pixels."""

    # --- Finder scaffold: a solid noir border frame ---
    frame_thickness_px: int = 14
    """Thickness of the black detection border, in canonical pixels."""
    frame_quiet_px: int = 24
    """White quiet zone outside the frame so it stands out for detection."""
    content_margin_px: int = 44
    """White gap between the frame's inner edge and the content (grid / strip). Wide
    enough to carry the noir chiaroscuro (vignette) around the scene."""
    strip_gap_px: int = 12
    """Gap between the grid and the Channel B strip below it."""

    # --- Rendering ---
    cell_px: int = 24
    """Edge length of one Channel A grid cell in the canonical (pre-styling) raster.
    Large enough that the halftone center (data) and outer ring (artwork) both have room."""
    cell_sample_inset: float = 0.30
    """Fraction trimmed from each side of a cell to bound the data patch. In halftone
    mode the un-sampled outer area carries the artwork, so a larger inset shows more
    picture (at some cost to sampling robustness)."""
    sample_inner_margin: float = 0.07
    """Extra inset (beyond ``cell_sample_inset``) the decoder samples within, to stay
    clear of the halftone artwork. The encoder compensates hatching brightness over
    this same inner window so the sampled mean matches the level's target gray."""
    seed: int = 0
    """Seed for any stochastic styling; pinned so output stays byte-stable."""
    hatched_data: bool = False
    """If set (halftone mode only), render the central data patch as line hatching whose
    mean equals the level, so the whole panel reads as engraving-style line art instead of
    flat gray dots. Off by default to keep canonical output byte-stable."""

    def __post_init__(self) -> None:
        if self.tonal_levels < 2:
            raise ValueError("tonal_levels must be >= 2")
        if not 0.0 <= self.tonal_margin < 0.5:
            raise ValueError("tonal_margin must be in [0.0, 0.5)")
        if not 0.0 < self.rs_parity_ratio < 1.0:
            raise ValueError("rs_parity_ratio must be in (0.0, 1.0)")
        if self.grid_cols < 1 or self.grid_rows < 1:
            raise ValueError("grid dimensions must be >= 1")
        if self.frame_thickness_px < 1 or self.frame_quiet_px < 1:
            raise ValueError("frame thickness and quiet zone must be >= 1")
        if self.motif_alphabet_size < 2:
            raise ValueError("motif_alphabet_size must be >= 2")
        if (self.motif_count * self.bits_per_motif) % 8 != 0:
            raise ValueError("motif_count * bits_per_motif must be a whole number of bytes")

    @property
    def grid_cells(self) -> int:
        """Total Channel A cells available for symbols."""
        return self.grid_cols * self.grid_rows

    @property
    def sample_inset(self) -> float:
        """Inset of the window the decoder samples (and the encoder compensates over)."""
        return min(0.49, self.cell_sample_inset + self.sample_inner_margin)

    @property
    def bits_per_cell(self) -> int:
        """Bits a single grid cell encodes at the configured tonal resolution."""
        return self.tonal_levels.bit_length() - 1

    @property
    def bits_per_motif(self) -> int:
        """Bits one Channel B strip module encodes."""
        return self.motif_alphabet_size.bit_length() - 1

    @property
    def channel_b_bytes(self) -> int:
        """Whole bytes Channel B's strip holds (MAGIC + LEN + Channel A checksum)."""
        return self.motif_count * self.bits_per_motif // 8

    @property
    def channel_a_capacity_bytes(self) -> int:
        """Whole bytes Channel A's grid holds (the RS codeword length)."""
        return self.grid_cells * self.bits_per_cell // 8

    @property
    def rs_blocks(self) -> list[tuple[int, int]]:
        """RS block layout as (data_bytes, parity_bytes) per block.

        A Reed-Solomon block over GF(2^8) holds at most 255 symbols, so the codeword
        is split into the fewest equal-ish blocks that each fit, with parity applied
        per block. The blocks' totals sum to ``channel_a_capacity_bytes``.
        """
        cap = self.channel_a_capacity_bytes
        nblocks = max(1, -(-cap // 255))  # ceil
        base, rem = divmod(cap, nblocks)
        blocks: list[tuple[int, int]] = []
        for i in range(nblocks):
            size = base + (1 if i < rem else 0)
            parity = max(1, min(size - 1, round(size * self.rs_parity_ratio)))
            blocks.append((size - parity, parity))
        return blocks

    @property
    def rs_parity_bytes(self) -> int:
        """Total RS parity symbols across all blocks."""
        return sum(parity for _, parity in self.rs_blocks)

    @property
    def rs_data_bytes(self) -> int:
        """Total frame bytes that fit across all blocks' data regions."""
        return sum(data for data, _ in self.rs_blocks)


DEFAULT = Config()

# Adaptive sizing: a small ladder of square grids (N x N). The encoder picks the
# smallest version that fits the payload; the decoder trials them (CRC validates the
# right one), so no explicit version marker is needed. Square keeps the 4-rotation
# trial valid. Ordered small -> large. ~22 / 58 / 109 / 173 text bytes at defaults.
GRID_VERSIONS: tuple[int, ...] = (16, 24, 32, 40)


def version_configs(base: Config) -> list[Config]:
    """``base`` re-gridded to each square version in :data:`GRID_VERSIONS` (small->large).

    Only the grid dimensions vary; every other format field is inherited from ``base``
    so the encoder and decoder agree on all the non-size tunables.
    """
    return [replace(base, grid_rows=n, grid_cols=n) for n in GRID_VERSIONS]


def select_grid(payload_len: int, base: Config) -> Config:
    """Smallest grid version whose RS data budget fits ``payload_len`` + frame overhead.

    Falls back to the largest version when nothing fits, so the caller's normal
    over-capacity error (``EccError`` in ``encode_codeword``) fires with its message.
    """
    need = payload_len + FRAME_OVERHEAD_BYTES
    versions = version_configs(base)
    for cfg in versions:
        if cfg.rs_data_bytes >= need:
            return cfg
    return versions[-1]


def candidate_configs(base: Config) -> list[Config]:
    """Configs the decoder should trial: ``base`` first (backward-compatible / custom
    grids), then any version grids not already covered. Deduped by grid dimensions."""
    seen: set[tuple[int, int]] = {(base.grid_rows, base.grid_cols)}
    out = [base]
    for cfg in version_configs(base):
        key = (cfg.grid_rows, cfg.grid_cols)
        if key not in seen:
            seen.add(key)
            out.append(cfg)
    return out

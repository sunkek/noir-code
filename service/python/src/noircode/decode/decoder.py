"""Decode orchestration: image -> DecodeResult.

Full dual-channel pipeline:

1. detect + rectify the panel to canonical (detect.py);
2. for each 90-degree orientation, sample Channel A (grid) and Channel B (motifs);
3. Channel B (high reliability) supplies the critical header bytes (MAGIC/LEN) — they
   overwrite Channel A's leading codeword bytes and clear those erasures, so a mangled
   header on A is recovered as long as B survived;
4. Reed-Solomon corrects Channel A; the frame's CRC validates the orientation;
5. Channel B's stored checksum of Channel A is recomputed and compared — a mismatch
   flags the read as suspect (cross-channel disagreement) rather than returning it
   silently.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import cv2
import numpy as np

from noircode.channels import checksum_byte, deinterleave, symbols_to_codeword
from noircode.config import Config, candidate_configs
from noircode.decode.detect import detect_frames, rectify_with
from noircode.decode.grid import GridSample, sample_grid, sample_grid_adaptive
from noircode.decode.motifs import sample_channel_b
from noircode.ecc import EccError, correct_codeword
from noircode.geometry import layout
from noircode.payload import FrameError, parse_frame


@dataclass(frozen=True)
class DecodeResult:
    """Structured decode outcome. ``failed_stage`` is None on success."""

    text: str | None
    confidence: float
    grid_erasures: int = 0
    motif_erasures: int = 0
    rotation: int | None = None
    cross_check: bool | None = None  # None = checksum unreadable; False = disagreement
    failed_stage: str | None = None

    @property
    def ok(self) -> bool:
        return self.text is not None


def _normalize_levels(canonical: np.ndarray) -> np.ndarray:
    """Stretch a rectified panel's tonal range back to a full 0..255.

    The tonal channel reads *absolute* gray (levels at 0/85/170/255), but a photo of a
    screen compresses and shifts that range (whites ~200, lifted blacks), pushing every
    cell's mean off its level → mass erasures. The rectified panel still contains the
    black frame (~0) and white quiet zone (~255) as anchors, so a global 2nd/98th
    percentile stretch remaps the range without the per-region distortion that broke an
    earlier local-flattening attempt. On a clean panel the range is already full, so
    this is ~identity.
    """
    lo, hi = np.percentile(canonical, 2), np.percentile(canonical, 98)
    if hi - lo < 1.0:
        return canonical
    out = (canonical.astype(np.float32) - lo) / (hi - lo) * 255.0
    clipped: np.ndarray = np.clip(out, 0.0, 255.0).astype(np.uint8)
    return clipped


def _flatfield_margin(canonical: np.ndarray, cfg: Config) -> np.ndarray:
    """Correct an uneven lighting gradient using the panel's white margin as reference.

    The inner margin (between the frame and the content) is known-white (255) in every
    panel, so the brightness observed there *is* the illumination. Fit a plane to those
    margin pixels and divide the whole panel by it, normalizing white back to 255 — which
    drags the tonal levels back onto their targets even under a strong side-light ramp.

    Unlike a blurred-field estimate, this is anchored to a true reference, so artwork and
    data (which never sit in the margin) can't bias it. On an evenly-lit/clean panel the
    plane is flat at ~255 and this is ~identity.
    """
    panel = layout(cfg)
    h, w = canonical.shape
    inner = cfg.frame_quiet_px + cfg.frame_thickness_px
    gx0, gy0, gx1, _ = panel.grid_box
    sy1 = panel.strip_boxes[-1][3]

    mask = np.zeros((h, w), dtype=bool)
    mask[inner : h - inner, inner : w - inner] = True
    mask[gy0:sy1, gx0:gx1] = False  # exclude the content (grid + strip)
    ys, xs = np.nonzero(mask)
    if len(ys) < 64:
        return canonical
    vals = canonical[ys, xs].astype(np.float32)
    # Keep the brighter margin pixels; drop any occluded/dark intrusions.
    keep = vals >= np.percentile(vals, 40)
    ys, xs, vals = ys[keep], xs[keep], vals[keep]
    if len(ys) < 64:
        return canonical

    a = np.c_[xs.astype(np.float32), ys.astype(np.float32), np.ones(len(xs), np.float32)]
    coef, *_ = np.linalg.lstsq(a, vals, rcond=None)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    field = np.maximum(coef[0] * xx + coef[1] * yy + coef[2], 1.0)
    out: np.ndarray = np.clip(canonical.astype(np.float32) * (255.0 / field), 0.0, 255.0).astype(
        np.uint8
    )
    return out


def _clahe_equalize(canonical: np.ndarray) -> np.ndarray:
    """Local-contrast rescue for screen captures.

    A photo of a monitor often compresses the tonal range non-uniformly: one region
    holds wide contrast, another is washed out by reflection or gamma rolloff. Global
    percentile stretching can't recover the washed region without crushing the rest.
    CLAHE re-spreads contrast inside small tiles, pulling each tile's tonal levels
    back onto their guard-band targets. On a clean panel this is near-identity since
    each tile is already full-range.
    """
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    out: np.ndarray = clahe.apply(canonical)
    return out


def _try_orientation(
    canonical: np.ndarray,
    cfg: Config,
    sampler: Callable[[np.ndarray, Config], GridSample] = sample_grid,
) -> DecodeResult | None:
    """Attempt a decode of one oriented canonical panel; None if it doesn't parse."""
    panel = layout(cfg)
    gx0, gy0, gx1, gy1 = panel.grid_box

    grid_sample = sampler(canonical[gy0:gy1, gx0:gx1], cfg)
    placed, placed_erasures = symbols_to_codeword(grid_sample.symbols, cfg.bits_per_cell)
    codeword_bytes, logical_erasures = deinterleave(placed, placed_erasures)
    codeword = bytearray(codeword_bytes)
    erasures = set(logical_erasures)

    motif_sample = sample_channel_b(canonical, cfg, panel)
    b_bytes, b_erased = symbols_to_codeword(motif_sample.symbols, cfg.bits_per_motif)
    b_erased_set = set(b_erased)

    # Channel B (high reliability) fills *erased* header bytes (MAGIC + LEN) on A. It
    # only substitutes where A is unknown — never overwrites a byte A read — so a
    # misread strip can't corrupt a good header; RS handles A's own errors.
    header_len = cfg.channel_b_bytes - 1
    for i in range(min(header_len, len(codeword))):
        if i in erasures and i not in b_erased_set:
            codeword[i] = b_bytes[i]
            erasures.discard(i)

    try:
        data, full = correct_codeword(bytes(codeword), sorted(erasures), cfg)
        payload = parse_frame(data)
        text = payload.decode("utf-8", errors="strict")
    except (EccError, FrameError, ValueError, UnicodeDecodeError):
        return None

    # Cross-channel checksum: compare B's stored checksum to the corrected A codeword.
    checksum_slot = cfg.channel_b_bytes - 1
    if checksum_slot in b_erased_set:
        cross_check: bool | None = None
    else:
        cross_check = b_bytes[checksum_slot] == checksum_byte(full)

    confidence = 1.0 - grid_sample.erasure_count / cfg.grid_cells
    if cross_check is False:
        confidence *= 0.5
    return DecodeResult(
        text=text,
        confidence=round(confidence, 4),
        grid_erasures=grid_sample.erasure_count,
        motif_erasures=motif_sample.erasure_count,
        cross_check=cross_check,
    )


def decode(img: np.ndarray, cfg: Config | None = None) -> DecodeResult:
    """Decode a (possibly warped/photographed/damaged) panel image.

    Adaptive sizing: the panel's grid version is not signalled, so each candidate grid
    (``cfg`` first, then the :data:`GRID_VERSIONS` ladder) is trialled across the four
    orientations. The frame CRC validates the right (version, rotation) pair; a wrong
    version samples noise and fails RS, so it is rejected, not returned.
    """
    cfg = cfg or Config()

    # A screenshot/photo may nest the panel inside other dark rings, so try several
    # candidate frames (largest first). For each: try every grid version and the four
    # orientations. The frame CRC validates the right (frame, version, rotation) triple.
    frames = detect_frames(img)
    if not frames:
        return DecodeResult(None, 0.0, failed_stage="detect: no frame-like quadrilateral found")

    for corners in frames:
        for ccfg in candidate_configs(cfg):
            base = _normalize_levels(rectify_with(img, ccfg, corners))
            # Try the plain normalized panel first (handles clean/mild capture), then a
            # margin-flat-fielded variant that rescues a strong lighting gradient, then a
            # CLAHE-equalized variant that rescues a screen capture's uneven local
            # contrast (gamma rolloff, monitor reflections). CRC accepts whichever
            # decodes, so additional variants only help, never regress.
            variants = (
                base,
                _normalize_levels(_flatfield_margin(base, ccfg)),
                _clahe_equalize(base),
            )
            # Two samplers per variant: the fixed-threshold sampler handles clean
            # captures and the adaptive (k-means) sampler rescues screen photos where
            # display gamma + camera tone-mapping shift the tonal levels off their
            # encoded targets. Adaptive runs second because it has higher variance:
            # on a clean panel the fixed quantizer is strictly more precise.
            samplers = (sample_grid, sample_grid_adaptive)
            for canonical in variants:
                for sampler in samplers:
                    for k in range(4):
                        oriented = np.rot90(canonical, k)
                        result = _try_orientation(oriented, ccfg, sampler=sampler)
                        if result is not None:
                            return DecodeResult(
                                text=result.text,
                                confidence=result.confidence,
                                grid_erasures=result.grid_erasures,
                                motif_erasures=result.motif_erasures,
                                rotation=k * 90,
                                cross_check=result.cross_check,
                            )

    return DecodeResult(
        None, 0.0, failed_stage="decode: no frame/version/orientation produced a valid frame"
    )

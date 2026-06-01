"""Robustness evaluation harness (Stage 6).

Sweeps payload length, RS parity, tonal levels and damage coverage; reports decode
success rate and per-panel capacity. Results are reproducible (seeded) and used to
choose sensible default config and document the art<->capacity<->robustness curve.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from noircode.config import Config
from noircode.decode.decoder import decode
from noircode.encode.encoder import encode
from noircode.simulate import occlude_grid, warp_panel


@dataclass(frozen=True)
class EvalPoint:
    tonal_levels: int
    rs_parity_ratio: float
    payload_len: int
    coverage: float
    styled: bool
    trials: int
    successes: int
    capacity_bytes: int

    @property
    def success_rate(self) -> float:
        return self.successes / self.trials if self.trials else 0.0


def _random_text(n: int, rng: np.random.Generator) -> str:
    return "".join(chr(int(rng.integers(32, 127))) for _ in range(n))


def evaluate_point(
    cfg: Config,
    payload_len: int,
    coverage: float,
    *,
    styled: bool = True,
    trials: int = 12,
    base_seed: int = 0,
) -> EvalPoint:
    """Measure decode success over ``trials`` warped + occluded captures."""
    successes = 0
    capacity = max(0, cfg.rs_data_bytes - 7)  # frame overhead
    payload_len = min(payload_len, capacity)
    for t in range(trials):
        rng = np.random.default_rng(base_seed + t)
        text = _random_text(payload_len, rng)
        panel = encode(text, cfg, style=styled)
        damaged = occlude_grid(panel, cfg, rng, coverage) if coverage > 0 else panel
        captured = warp_panel(damaged, rng)
        res = decode(captured, cfg)
        if res.ok and res.text == text and res.cross_check is not False:
            successes += 1
    return EvalPoint(
        tonal_levels=cfg.tonal_levels,
        rs_parity_ratio=cfg.rs_parity_ratio,
        payload_len=payload_len,
        coverage=coverage,
        styled=styled,
        trials=trials,
        successes=successes,
        capacity_bytes=capacity,
    )


def default_sweep(base: Config | None = None, *, trials: int = 12) -> list[EvalPoint]:
    """A representative sweep across parity, tonal levels and damage."""
    base = base or Config()
    points: list[EvalPoint] = []
    for tonal in (4, 8):
        for parity in (0.25, 0.40, 0.55):
            cfg = replace(base, tonal_levels=tonal, rs_parity_ratio=parity)
            payload = max(1, (cfg.rs_data_bytes - 7) // 2)
            for coverage in (0.0, 0.1, 0.2, 0.3):
                points.append(evaluate_point(cfg, payload, coverage, trials=trials))
    return points


def format_report(points: list[EvalPoint]) -> str:
    """Render a sweep as a fixed-width table."""
    header = (
        f"{'levels':>6} {'parity':>6} {'payload':>7} {'cap':>4} "
        f"{'cover':>5} {'styled':>6} {'success':>7}"
    )
    lines = [header, "-" * len(header)]
    for p in points:
        lines.append(
            f"{p.tonal_levels:>6} {p.rs_parity_ratio:>6.2f} {p.payload_len:>7} "
            f"{p.capacity_bytes:>4} {p.coverage:>5.2f} {str(p.styled):>6} "
            f"{p.success_rate:>6.0%}"
        )
    return "\n".join(lines)

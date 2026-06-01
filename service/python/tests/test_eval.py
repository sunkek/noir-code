"""Stage 6: the eval harness is reproducible and reports sane numbers."""

from noircode.config import Config
from noircode.eval import default_sweep, evaluate_point, format_report


def test_clean_capture_high_success() -> None:
    cfg = Config()
    point = evaluate_point(cfg, payload_len=10, coverage=0.0, trials=8)
    assert point.success_rate == 1.0


def test_parity_trades_capacity_for_robustness() -> None:
    from dataclasses import replace

    low = replace(Config(), rs_parity_ratio=0.20)
    high = replace(Config(), rs_parity_ratio=0.55)
    # More parity -> fewer payload bytes (capacity) but a larger erasure budget.
    assert high.rs_data_bytes < low.rs_data_bytes
    assert high.rs_parity_bytes > low.rs_parity_bytes


def test_sweep_is_reproducible() -> None:
    a = default_sweep(trials=4)
    b = default_sweep(trials=4)
    assert [p.successes for p in a] == [p.successes for p in b]


def test_report_renders() -> None:
    report = format_report(default_sweep(trials=2))
    assert "success" in report
    assert "levels" in report

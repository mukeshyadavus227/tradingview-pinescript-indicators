"""
Research ↔ production parity for the allocator: replaying the Phase 4 trade
lists through server.allocator must reproduce the numbers in
research/out/phase4_summary.json. Skipped when the regenerable trade lists
(research/out/final_*.csv, gitignored) are absent — run
`python research/final_v3.py && python research/portfolio_sim.py` first.
"""
import json, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research" / "out"


@pytest.mark.skipif(not (OUT / "final_SWING_v3.csv").exists() or not (OUT / "phase4_summary.json").exists(),
                    reason="regenerable research outputs not present")
def test_allocator_reproduces_phase4_summary():
    sys.path.insert(0, str(ROOT / "research"))
    import portfolio_sim as ps
    ref = json.load(open(OUT / "phase4_summary.json"))
    df = ps.load(); test = df[df.date >= ps.SPLIT]
    for rule in ("fifo", "per_bar"):
        eq, tr = ps.run(test, 10, rule, True, 1.0)
        m = ps.metrics(eq, tr, rule)
        r = ref[f"test 2021+|1.0|10|{rule}|True"]
        assert abs(m["cagr"] - r["cagr"]) < 1e-9 and abs(m["trades_yr"] - r["trades_yr"]) < 1e-9

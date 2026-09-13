from server.allocator import Allocator, AllocatorConfig, Candidate, OpenPosition, strategy_key

EQ = 100_000.0


def op(sym, prof="SWING", key="S3-SW", risk=1000.0):
    return OpenPosition(sym, prof, key, risk)


def test_symbol_uniqueness_across_profiles():
    a = Allocator(AllocatorConfig(max_positions=10))
    d = a.admit(Candidate("AAPL", "POSITIONAL", "S4-POS"), [op("AAPL")], EQ)
    assert not d.admit and "symbol" in d.reason


def test_slot_cap():
    a = Allocator(AllocatorConfig(max_positions=2))
    d = a.admit(Candidate("MSFT", "SWING", "S3-SW"), [op("A"), op("B")], EQ)
    assert not d.admit and "slots" in d.reason


def test_heat_cap_binds_before_slots():
    a = Allocator(AllocatorConfig(max_positions=10, risk_pct=1.0, max_heat_pct=3.0))
    d = a.admit(Candidate("MSFT", "SWING", "S3-SW"), [op("A"), op("B"), op("C")], EQ)   # 3% open + 1% new > 3%
    assert not d.admit and "heat" in d.reason


def test_risk_dollars_is_fraction_of_equity():
    a = Allocator(AllocatorConfig(risk_pct=1.5))
    d = a.admit(Candidate("MSFT", "SWING", "S3-SW"), [], 200_000.0)
    assert d.admit and abs(d.risk_dollars - 3000.0) < 1e-9


def test_same_bar_batch_ranks_per_bar_and_counts_admissions():
    a = Allocator(AllocatorConfig(max_positions=2, rule="per_bar"))
    cands = [Candidate("X", "POSITIONAL", "S4-POS", 90), Candidate("Y", "SWING", "S3-SW", 60), Candidate("Z", "SWING", "S1-SW", 40)]
    ds = a.admit_batch(cands, [], EQ)
    admitted = [d.candidate.symbol for d in ds if d.admit]
    assert admitted == ["Z", "Y"]          # S1 first, then S3 (per-bar), S4-POS loses the last slot


def test_priority_rule_prefers_positional_s4():
    a = Allocator(AllocatorConfig(max_positions=1, rule="priority"))
    ds = a.admit_batch([Candidate("Y", "SWING", "S3-SW"), Candidate("X", "POSITIONAL", "S4-POS")], [], EQ)
    assert [d.candidate.symbol for d in ds if d.admit] == ["X"]


def test_reserve_rule_keeps_half_for_each_profile():
    a = Allocator(AllocatorConfig(max_positions=4, rule="reserve"))
    opens = [op("A"), op("B")]                                   # SWING half full
    assert not a.admit(Candidate("C", "SWING", "S3-SW"), opens, EQ).admit
    assert a.admit(Candidate("D", "POSITIONAL", "S4-POS"), opens, EQ).admit


def test_strategy_key_mapping():
    assert strategy_key("SWING", "RSI_MeanReversion") == "S1-SW"
    assert strategy_key("POSITIONAL", "MultiTF_Trend") == "S4-POS"
    assert strategy_key("swing", 3) == "S3-SW"

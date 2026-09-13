import json, pytest
from server.schema import SignalV2

# Shaped exactly as asr_engine.pine v3 builds it (ENTRY on S3, then a MODIFY heartbeat bar).
ENTRY = json.loads('''{"schema_version":"2.1.0","signal_id":"AAPL|SWING|1789133400000|ENTRY|12","profile":"SWING","account_route":"IBKR_TAXABLE","manual_only":false,
"symbol":"AAPL","action":"BUY","event":"ENTRY","events":[{"type":"ENTRY","price":332.27,"stop":325.10,"partial_at":339.44,"partial_pct":50}],
"qty":1,"order_type":"MKT","price":332.27,"stop":325.10,"tif":"DAY","sec_type":"STK","exchange":"","strategy":"EMA_VWAP_Momentum",
"comment":"ASR2|SWING|MOM|sc=74|cf=0.60|rr=1.7|sl=325.10|tp=344.40|rg=NEUTRAL|rv=61|cmp=63.2","confidence":0.60,
"thesis":{"direction":"LONG","horizon_days":15,"expected_move_atr":3.0},
"desired_state":{"side":"LONG","strategy":"EMA_VWAP_Momentum","entry_ref":332.27,"risk":7.17,"stop":325.10,"size_pct_open":100,"partial_at":339.44,"partial_pct":50,
"trail":{"type":"CHANDELIER_ATR","k":3,"active":false,"level":null},"breakeven_after_partial":true,"time_stop_at":null,"bars_in_trade":0},
"sizing":{"stop_distance":7.17,"stop_pct":2.16,"rr_ratio":1.7,"atr_chart":3.98,"atr_daily":3.98},
"scores":{"conviction":74,"composite":63.2,"winner":"MOM","s1":0,"s3":74,"s4":0,"calibrated":false},
"regime":{"label":"NEUTRAL","confidence":0,"secondary":"BREAKOUT","secondary_score":40,"trend":10,"breakout":40,"meanrev":20,"momentum":30},
"context":{"feature_basis":"daily","rsi":58.1,"adx":19.2,"chop":52.3,"atr_pctile":44,"rel_vol_pctile":61,"roc_20d":3.1,"roc_60d":8.2,"roc_126d":12.5,"mom_12_1":30.1,"dist_52wk_hi":6.2,"dist_52wk_lo":93.8,"rsi_daily":58.1,"adx_daily":19.2,"adv20_usd":11234567890,"avg_gap_pct":0.61},
"meta":{"bar_time":1789133400000,"bar_close_time":1789156800000,"tf":"D","warmup_ok":true,"bars_per_day":1,"bpd_drift_pct":0,"script_version":"3.0.0"}}''')

MODIFY = json.loads('''{"schema_version":"2.1.0","signal_id":"AAPL|SWING|1789219800000|MODIFY|13","profile":"SWING","account_route":"IBKR_TAXABLE","manual_only":false,
"symbol":"AAPL","action":"MANAGE","event":"MODIFY","events":[{"type":"MODIFY","stop":331.00,"from":325.10}],
"qty":1,"order_type":"MKT","price":335.10,"stop":331.00,"tif":"DAY","sec_type":"STK","exchange":"","strategy":"None","comment":"ASR2|SWING|--|sc=0|cf=0.60|rr=0|sl=0|tp=0|rg=NEUTRAL|rv=55|cmp=30","confidence":0.60,
"desired_state":{"side":"LONG","strategy":"EMA_VWAP_Momentum","entry_ref":332.27,"risk":7.17,"stop":331.00,"size_pct_open":50,"partial_at":null,"partial_pct":50,
"trail":{"type":"CHANDELIER_ATR","k":3,"active":true,"level":331.00},"breakeven_after_partial":true,"time_stop_at":null,"bars_in_trade":3},
"meta":{"bar_time":1789219800000,"tf":"D","warmup_ok":true,"script_version":"3.0.0"}}''')


def test_entry_parses_and_is_entry():
    s = SignalV2.model_validate(ENTRY)
    assert s.is_entry and s.symbol == "AAPL" and s.stop == 325.10
    assert s.desired_state.partial_at == 339.44 and s.desired_state.trail.active is False
    assert s.events[0].type == "ENTRY" and s.idempotency_key == s.idempotency_key


def test_modify_parses_manage():
    s = SignalV2.model_validate(MODIFY)
    assert not s.is_entry and s.action == "MANAGE" and s.event == "MODIFY"
    assert s.events[0].from_ == 325.10 and s.desired_state.size_pct_open == 50


def test_v1_payload_still_validates():
    s = SignalV2.model_validate({"symbol": "mnq", "action": "BUY", "qty": 1, "sec_type": "FUT"})
    assert s.symbol == "MNQ" and s.confidence == 0.6 and s.desired_state is None


def test_stale_schema_rejected():
    bad = dict(ENTRY); bad["schema_version"] = "2.0.0"
    with pytest.raises(ValueError):
        SignalV2.model_validate(bad)


def test_warmup_rejected():
    bad = json.loads(json.dumps(ENTRY)); bad["meta"]["warmup_ok"] = False
    with pytest.raises(ValueError):
        SignalV2.model_validate(bad)


def test_manage_without_event_rejected():
    bad = dict(MODIFY); bad["event"] = None
    with pytest.raises(ValueError):
        SignalV2.model_validate(bad)

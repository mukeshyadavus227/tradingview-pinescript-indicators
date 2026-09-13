import copy
from server.schema import SignalV2
from server.reconciler import reconcile, BrokerPosition, BrokerOrder
from server.tests.test_schema import ENTRY, MODIFY


def acts(intents):
    return [i.action for i in intents]


def test_entry_places_entry_stop_and_partial_limit():
    s = SignalV2.model_validate(ENTRY)
    out = reconcile(s, None, [], entry_qty=100)
    assert acts(out) == ["PLACE_ENTRY", "PLACE_STOP", "PLACE_LIMIT"]
    assert out[1].price == 325.10 and out[2].qty == 50 and out[2].price == 339.44


def test_modify_replaces_stop_when_price_differs():
    s = SignalV2.model_validate(MODIFY)                      # size_pct_open 50 → broker should hold half
    pos = BrokerPosition("AAPL", 50)
    out = reconcile(s, pos, [BrokerOrder("o1", "AAPL", "STOP", 325.10, 50)], entry_qty=0)
    assert acts(out) == ["REPLACE_STOP"] and out[0].price == 331.00 and out[0].order_id == "o1"


def test_idempotent_when_broker_matches():
    s = SignalV2.model_validate(MODIFY)
    out = reconcile(s, BrokerPosition("AAPL", 50), [BrokerOrder("o1", "AAPL", "STOP", 331.00, 50)], entry_qty=0)
    assert out == []


def test_partial_missed_sells_the_difference_and_cancels_limit():
    s = SignalV2.model_validate(MODIFY)                      # engine says 50% open, broker still holds 100
    out = reconcile(s, BrokerPosition("AAPL", 100), [BrokerOrder("o1", "AAPL", "STOP", 325.10, 100), BrokerOrder("o2", "AAPL", "LIMIT", 339.44, 50)], entry_qty=0, full_qty=100)
    assert acts(out) == ["SELL_QTY", "REPLACE_STOP", "CANCEL"]
    assert out[0].qty == 50 and out[1].qty == 50


def test_flat_cancels_and_flattens():
    s = SignalV2.model_validate(MODIFY)
    d = copy.deepcopy(MODIFY); d["desired_state"]["side"] = "FLAT"; d["event"] = "EXIT"; d["events"] = [{"type": "EXIT", "price": 331.0, "reason": "TRAIL"}]
    s = SignalV2.model_validate(d)
    out = reconcile(s, BrokerPosition("AAPL", 50), [BrokerOrder("o1", "AAPL", "STOP", 331.0, 50)], entry_qty=0)
    assert acts(out) == ["CANCEL", "FLATTEN"] and out[1].qty == 50


def test_heartbeat_without_position_does_not_chase():
    d = copy.deepcopy(MODIFY); d["event"] = "HEARTBEAT"; d["events"] = [{"type": "HEARTBEAT"}]
    s = SignalV2.model_validate(d)
    out = reconcile(s, None, [], entry_qty=100)
    assert acts(out) == ["NOTE"]

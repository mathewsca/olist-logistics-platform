import math

import pandas as pd
import pytest

from olist_platform.features import history_snapshot, lookup_history, point_in_time_history
from olist_platform.features.seller_history import PLATFORM_KEY, SMOOTHING_WEIGHT


def deliveries(*rows):
    return pd.DataFrame(rows, columns=["seller_id", "delivered_at", "is_late", "delivery_days"])


def orders(*rows):
    return pd.DataFrame(rows, columns=["seller_id", "purchased_at"])


def test_order_still_in_transit_at_purchase_does_not_count():
    # s1 bought on Jan 1 but delivered (late) on Jan 20: unknown when the Jan 10 order is placed.
    events = deliveries(("s1", "2018-01-20", True, 19.0))
    history = point_in_time_history(orders(("s1", "2018-01-10")), events)
    assert history.loc[0, "seller_prior_deliveries"] == 0
    assert math.isnan(history.loc[0, "seller_prior_mean_delivery_days"])


def test_delivery_at_the_same_instant_as_the_purchase_is_excluded():
    events = deliveries(("s1", "2018-01-10 12:00", True, 5.0))
    history = point_in_time_history(orders(("s1", "2018-01-10 12:00")), events)
    assert history.loc[0, "seller_prior_deliveries"] == 0


def test_counts_only_the_same_seller_and_earlier_deliveries():
    events = deliveries(
        ("s1", "2018-01-02", True, 4.0),
        ("s1", "2018-01-05", False, 6.0),
        ("s2", "2018-01-03", True, 9.0),
        ("s1", "2018-02-01", True, 30.0),
    )
    history = point_in_time_history(orders(("s1", "2018-01-10")), events)
    row = history.loc[0]
    assert row["seller_prior_deliveries"] == 2
    assert row["seller_prior_mean_delivery_days"] == pytest.approx(5.0)
    platform_rate = 2 / 3
    expected = (1 + SMOOTHING_WEIGHT * platform_rate) / (2 + SMOOTHING_WEIGHT)
    assert row["seller_prior_late_rate"] == pytest.approx(expected)


def test_keeps_the_input_order_and_index():
    events = deliveries(("s1", "2018-01-02", True, 4.0))
    frame = orders(("s1", "2018-03-01"), ("s1", "2018-01-01"))
    frame.index = [10, 20]
    history = point_in_time_history(frame, events)
    assert list(history.index) == [10, 20]
    assert list(history["seller_prior_deliveries"]) == [1, 0]


def test_new_seller_without_platform_history_gets_zero_rate():
    history = point_in_time_history(orders(("s9", "2018-01-01")), deliveries())
    assert history.loc[0, "seller_prior_late_rate"] == 0


@pytest.mark.parametrize(
    "extra_events",
    [
        pytest.param((), id="plain"),
        pytest.param((("s1", "2018-01-05", True, 7.0),), id="tied-delivery-times"),
        pytest.param((("s1", "2018-01-10", True, 8.0),), id="event-exactly-at-as-of"),
    ],
)
def test_snapshot_matches_point_in_time_at_the_same_instant(extra_events):
    events = deliveries(
        ("s1", "2018-01-02", True, 4.0),
        ("s1", "2018-01-05", False, 6.0),
        ("s2", "2018-01-03", False, 9.0),
        *extra_events,
    )
    as_of = pd.Timestamp("2018-01-10")
    snapshot = history_snapshot(events, as_of)
    sellers = ["s1", "s2", "unknown"]
    served = lookup_history(pd.Series(sellers), snapshot)
    trained = point_in_time_history(orders(*((s, as_of) for s in sellers)), events)
    pd.testing.assert_frame_equal(served.reset_index(drop=True), trained.reset_index(drop=True))


def test_unseen_seller_uses_the_platform_row():
    snapshot = history_snapshot(
        deliveries(("s1", "2018-01-02", True, 4.0)), pd.Timestamp("2018-02-01")
    )
    served = lookup_history(pd.Series(["unknown"]), snapshot)
    assert served.iloc[0]["seller_prior_deliveries"] == 0
    assert served.iloc[0]["seller_prior_late_rate"] == pytest.approx(1.0)
    assert PLATFORM_KEY in snapshot.index

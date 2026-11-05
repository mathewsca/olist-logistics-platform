import pandas as pd
import pytest

from olist_platform.models.data import prepare
from olist_platform.monitoring.retrain import known_rows
from olist_platform.monitoring.windows import (
    MONITORED_MONTHS,
    FitWindow,
    bootstrap_window,
    challenger_window,
    evaluated_at,
    gate_window,
    parse_month,
)
from tests.model_data import synthetic_deliveries


def test_a_month_is_evaluated_after_its_labels_matured_for_one_month():
    assert evaluated_at(pd.Period("2018-04", "M")) == pd.Timestamp("2018-06-01")
    assert evaluated_at(pd.Period("2018-08", "M")) == pd.Timestamp("2018-10-01")


def test_bootstrap_only_knows_what_existed_when_the_simulation_starts():
    window = bootstrap_window()
    assert window.label_cutoff == MONITORED_MONTHS[0].start_time == pd.Timestamp("2018-04-01")
    assert window.data_end == pd.Timestamp("2018-03-01")
    assert window.validation_start == pd.Timestamp("2018-01-01")


def test_gate_fit_knows_nothing_that_happened_during_the_month():
    window = gate_window(pd.Period("2018-05", "M"))
    assert window.label_cutoff == pd.Timestamp("2018-05-01")
    assert window.data_end == pd.Timestamp("2018-04-01")


def test_promoted_refit_uses_everything_known_at_the_evaluation():
    window = challenger_window(pd.Period("2018-05", "M"))
    assert window.label_cutoff == pd.Timestamp("2018-07-01")
    assert window.data_end == pd.Timestamp("2018-06-01")


def test_known_rows_drop_orders_not_yet_delivered_at_the_cutoff():
    data = prepare(synthetic_deliveries())
    # Synthetic deliveries take under a month, so a short gap is needed to leave some in transit.
    window = FitWindow(pd.Timestamp("2018-03-01"), pd.Timestamp("2018-03-06"))
    rows = known_rows(data, window)
    assert not rows.empty
    assert (rows["purchased_at"] < window.data_end).all()
    assert (rows["delivered_to_customer_at"] < window.label_cutoff).all()
    bought_in_time = data.rows[data.rows["purchased_at"] < window.data_end]
    assert len(rows) < len(bought_in_time)


@pytest.mark.parametrize("value", ["2018-03", "2018-09"])
def test_parse_month_rejects_months_outside_the_simulation(value):
    with pytest.raises(ValueError, match="outside the simulated months"):
        parse_month(value)

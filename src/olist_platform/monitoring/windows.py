"""Calendar of the production simulation: which data each step may see."""

from dataclasses import dataclass

import pandas as pd

from olist_platform.monitoring import SIMULATED_MONTHS

# The months the simulation treats as new data, one at a time, in order.
MONITORED_MONTHS = tuple(pd.Period(month, freq="M") for month in SIMULATED_MONTHS)
SIMULATION_START = MONITORED_MONTHS[0].start_time
# Labels need time to arrive: a month is evaluated one full month after it closes, when most of its
# deliveries (and nearly all late ones) are known.
LABEL_DELAY_MONTHS = 1
VALIDATION_MONTHS = 2


@dataclass(frozen=True)
class FitWindow:
    """Purchases before ``data_end``, labels delivered before ``label_cutoff``."""

    data_end: pd.Timestamp
    label_cutoff: pd.Timestamp

    @property
    def validation_start(self) -> pd.Timestamp:
        return self.data_end - pd.DateOffset(months=VALIDATION_MONTHS)


def evaluated_at(month: pd.Period) -> pd.Timestamp:
    """Simulated date when ``month`` is monitored: its labels have matured for one month."""
    return (month + 1 + LABEL_DELAY_MONTHS).start_time


def bootstrap_window() -> FitWindow:
    """The model in production when the simulation starts, built only from what was known then."""
    return known_at(SIMULATION_START)


def known_at(cutoff: pd.Timestamp) -> FitWindow:
    """What a refit at ``cutoff`` may use: labels before it, purchases old enough to have them."""
    return FitWindow(cutoff - pd.DateOffset(months=LABEL_DELAY_MONTHS), cutoff)


def gate_window(month: pd.Period) -> FitWindow:
    """The retraining recipe as it would have run when ``month`` began.

    The quality gate judges this fit on ``month``: it saw neither the month's purchases nor any
    label that arrived during it, like the champion that served the month.
    """
    return known_at(month.start_time)


def challenger_window(month: pd.Period) -> FitWindow:
    """What a promoted challenger is refit on: everything known when ``month`` is evaluated."""
    return known_at(evaluated_at(month))


def parse_month(value: str) -> pd.Period:
    """``YYYY-MM`` -> monthly period, restricted to the simulated months."""
    month = pd.Period(value, freq="M")
    if month not in MONITORED_MONTHS:
        raise ValueError(f"{value} is outside the simulated months {MONITORED_MONTHS}")
    return month

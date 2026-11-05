"""Temporal train / validation / test split by purchase date (never random)."""

from dataclasses import dataclass

import pandas as pd

VALIDATION_START = pd.Timestamp("2018-04-01")
TEST_START = pd.Timestamp("2018-06-01")


@dataclass(frozen=True)
class Split:
    """Rows of each period, oldest to newest."""

    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame

    def summary(self) -> pd.DataFrame:
        """Period, rows and late rate of each part."""
        records = []
        for name, frame in (
            ("train", self.train),
            ("validation", self.validation),
            ("test", self.test),
        ):
            records.append(
                {
                    "part": name,
                    "first_purchase": frame["purchased_at"].min().date(),
                    "last_purchase": frame["purchased_at"].max().date(),
                    "rows": len(frame),
                    "late_rate": frame["is_late"].mean(),
                }
            )
        return pd.DataFrame(records)


def temporal_split(
    rows: pd.DataFrame,
    validation_start: pd.Timestamp = VALIDATION_START,
    test_start: pd.Timestamp = TEST_START,
) -> Split:
    """Split on purchase date: train < validation_start <= validation < test_start <= test."""
    if validation_start >= test_start:
        raise ValueError("validation_start must be earlier than test_start")
    purchased_at = pd.to_datetime(rows["purchased_at"])
    return Split(
        train=rows[purchased_at < validation_start].reset_index(drop=True),
        validation=rows[
            (purchased_at >= validation_start) & (purchased_at < test_start)
        ].reset_index(drop=True),
        test=rows[purchased_at >= test_start].reset_index(drop=True),
    )

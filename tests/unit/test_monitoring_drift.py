import numpy as np
import pandas as pd
import pytest

from olist_platform.monitoring.drift import drift_summary


def features(rows: int, shift: float, sp_share: float, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame(
        {
            "distance_km": rng.normal(500 + shift, 100, rows),
            "items_value": rng.gamma(2, 60, rows),
            "origin_state": rng.choice(["SP", "RJ"], rows, p=[sp_share, 1 - sp_share]).astype(
                object
            ),
        }
    )
    frame.loc[::40, "items_value"] = np.nan
    return frame


# Evidently switches from statistical tests (p-values) to distances above 1,000 rows.
@pytest.mark.parametrize("rows", [300, 4000])
def test_shifted_features_are_flagged_and_stable_ones_are_not(rows):
    summary = drift_summary(features(rows, 0, 0.5, 1), features(rows, 300, 0.9, 2))
    assert summary.drifted == ["distance_km", "origin_state"]
    assert summary.share == pytest.approx(2 / 3)
    assert set(summary.scores) == {"distance_km", "items_value", "origin_state"}


def test_same_distribution_has_no_drift():
    summary = drift_summary(features(4000, 0, 0.5, 1), features(4000, 0, 0.5, 2))
    assert summary.drifted == []
    assert summary.share == 0


def test_writes_the_html_report(tmp_path):
    path = tmp_path / "2018-04" / "drift_report.html"
    drift_summary(features(300, 0, 0.5, 1), features(300, 0, 0.5, 2), path)
    assert path.stat().st_size > 0


def test_rejects_different_columns():
    with pytest.raises(ValueError, match="same feature columns"):
        drift_summary(features(50, 0, 0.5, 1), features(50, 0, 0.5, 2).drop(columns="items_value"))

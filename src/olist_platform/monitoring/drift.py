"""Data drift of the served features against the champion's training reference (Evidently)."""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from olist_platform.features import CATEGORICAL_FEATURES

# Evidently's default per-column decision: share of drifted columns is compared to the trigger in
# ``performance``, so the preset's own dataset-level verdict is not used.
PRESET_DRIFT_SHARE = 0.5


@dataclass(frozen=True)
class DriftSummary:
    """Share of drifted features and their names, as Evidently decided them."""

    share: float
    drifted: list[str]
    scores: dict[str, float]


def _is_drifted(method: str, score: float, threshold: float) -> bool:
    # Statistical tests report a p-value (drift when small); the large-sample defaults report a
    # distance (drift when large).
    if "p_value" in method:
        return score < threshold
    return score >= threshold


def _definition(columns: list[str]):
    from evidently import DataDefinition

    return DataDefinition(
        numerical_columns=[c for c in columns if c not in CATEGORICAL_FEATURES],
        categorical_columns=[c for c in columns if c in CATEGORICAL_FEATURES],
    )


def drift_summary(
    reference: pd.DataFrame, current: pd.DataFrame, report_path: Path | None = None
) -> DriftSummary:
    """Run the data drift preset; writes the HTML report when ``report_path`` is given."""
    from evidently import Dataset, Report
    from evidently.presets import DataDriftPreset

    columns = list(reference.columns)
    if list(current.columns) != columns:
        raise ValueError("reference and current must have the same feature columns")
    definition = _definition(columns)
    snapshot = Report([DataDriftPreset(drift_share=PRESET_DRIFT_SHARE)]).run(
        Dataset.from_pandas(current, data_definition=definition),
        Dataset.from_pandas(reference, data_definition=definition),
    )

    share, count, scores, drifted = None, None, {}, []
    for metric in snapshot.dict()["metrics"]:
        config = metric["config"]
        if config["type"].endswith(":DriftedColumnsCount"):
            count, share = int(metric["value"]["count"]), float(metric["value"]["share"])
        elif config["type"].endswith(":ValueDrift"):
            score = float(metric["value"])
            scores[config["column"]] = score
            if _is_drifted(config["method"], score, config["threshold"]):
                drifted.append(config["column"])
    if share is None or count != len(drifted):
        raise RuntimeError(
            f"Per-column drift ({len(drifted)}) disagrees with Evidently's count ({count})"
        )

    if report_path is not None:
        report_path = Path(report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot.save_html(str(report_path))
    return DriftSummary(share=share, drifted=sorted(drifted), scores=scores)

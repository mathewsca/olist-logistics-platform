"""SHAP explanations of the tree champion: global importance and individual orders."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

# A sample keeps TreeExplainer fast; the mean |SHAP| ranking is stable well before this size.
SHAP_SAMPLE_SIZE = 3000
TOP_CONTRIBUTIONS = 5


@dataclass(frozen=True)
class Explanation:
    """Mean |SHAP| per feature and a few annotated orders."""

    importance: pd.DataFrame
    examples: list[dict]


def _positive_class(values) -> np.ndarray:
    if isinstance(values, list):
        return np.asarray(values[1])
    values = np.asarray(values)
    return values[..., 1] if values.ndim == 3 else values


def shap_values(pipeline: Pipeline, features: pd.DataFrame) -> pd.DataFrame:
    """Per-row SHAP values (log-odds for classifiers, days for regressors), columns = features."""
    import shap

    transformed = pipeline[:-1].transform(features)
    explainer = shap.TreeExplainer(pipeline[-1])
    values = _positive_class(explainer.shap_values(transformed))
    return pd.DataFrame(values, index=features.index, columns=transformed.columns)


def _contributions(row_values: pd.Series, row_features: pd.Series) -> list[dict]:
    top = row_values.abs().sort_values(ascending=False).head(TOP_CONTRIBUTIONS).index
    return [
        {"feature": name, "value": row_features[name], "shap": float(row_values[name])}
        for name in top
    ]


def pick_examples(target: pd.Series, scores: np.ndarray) -> dict[str, int]:
    """Index labels of the riskiest and safest late orders and of a typical on-time order."""
    # Labels speak of the explained model's ranking, not of a threshold: when a linear model is the
    # champion, the decision threshold belongs to another model.
    scores = pd.Series(scores, index=target.index)
    late = scores[target.astype(bool)]
    on_time = scores[~target.astype(bool)]
    median_on_time = (on_time - on_time.median()).abs().idxmin()
    return {
        "atrasado com o maior risco previsto": late.idxmax(),
        "atrasado com o menor risco previsto": late.idxmin(),
        "entrega no prazo típica (risco mediano)": median_on_time,
    }


def explain(
    pipeline: Pipeline, features: pd.DataFrame, target: pd.Series, scores: np.ndarray
) -> Explanation:
    """Global importance on a sample of ``features`` plus three individual explanations."""
    sample = features.sample(min(SHAP_SAMPLE_SIZE, len(features)), random_state=0)
    values = shap_values(pipeline, sample)
    importance = (
        values.abs()
        .mean()
        .sort_values(ascending=False)
        .rename("mean_abs_shap")
        .rename_axis("feature")
        .reset_index()
    )

    picks = pick_examples(target, scores)
    # With a single late order, two picks are the same row; duplicate labels would break .loc below.
    unique_picks = list(dict.fromkeys(picks.values()))
    example_values = shap_values(pipeline, features.loc[unique_picks])
    examples = [
        {
            "label": label,
            "score": float(pd.Series(scores, index=features.index)[index]),
            "is_late": bool(target[index]),
            "contributions": _contributions(example_values.loc[index], features.loc[index]),
        }
        for label, index in picks.items()
    ]
    return Explanation(importance=importance, examples=examples)

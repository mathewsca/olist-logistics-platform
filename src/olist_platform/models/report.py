"""Markdown report of a training run: the only source of the modelling numbers in the README."""

import math
from datetime import date
from pathlib import Path

from olist_platform.analytics.formatting import format_metric, table_lines
from olist_platform.models.train import (
    CHAMPION_ALIAS,
    CLASSIFIER_NAME,
    REGRESSOR_NAME,
    MethodResult,
    TrainingOutcome,
)

REPORT_PATH = Path("docs/modelagem.md")

METHOD_LABELS = {
    "majority_class": "Classe majoritária (= confiar no prazo da Olist)",
    "route_slack_rule": "Regra: mediana da rota − prazo prometido",
    "logistic_regression": "Regressão logística (classes balanceadas)",
    "lightgbm": "LightGBM",
    "lightgbm_weighted": "LightGBM (classe positiva reponderada)",
    "olist_estimate": "Prazo estimado da Olist",
    "train_median": "Mediana do treino",
    "route_median": "Mediana da rota UF → UF",
    "ridge_regression": "Regressão linear (Ridge)",
}
PART_LABELS = {"train": "treino", "validation": "validação", "test": "teste"}


def _label(result: MethodResult, champion: str) -> str:
    label = METHOD_LABELS.get(result.name, result.name)
    return f"**{label}** (campeão)" if result.name == champion else label


def split_section(outcome: TrainingOutcome) -> list[str]:
    """Rows and late rate of each period."""
    rows = [
        [
            PART_LABELS[row.part],
            f"{row.first_purchase} a {row.last_purchase}",
            format_metric(row.rows, 0),
            format_metric(row.late_rate * 100, 1),
        ]
        for row in outcome.split.summary().itertuples()
    ]
    return [
        "## Divisão temporal",
        "",
        "Por data da compra, do mais antigo ao mais recente. O limiar e o campeão são escolhidos "
        "na validação; o teste é olhado uma única vez.",
        "",
        *table_lines(
            ["parte", "compras", "entregas", "atraso_pct"], ["---", "---", "--:", "--:"], rows
        ),
        "",
    ]


def classification_section(outcome: TrainingOutcome) -> list[str]:
    """Metrics of every classifier and baseline on validation and test."""
    task = outcome.classification
    metrics = ["pr_auc", "roc_auc", "f1", "precision", "recall", "brier"]
    header = ["método", "parte", *metrics, "sinalizados_pct"]
    rows = []
    for result in task.results:
        for part in ("validation", "test"):
            values = getattr(result, part)
            rows.append(
                [
                    _label(result, task.champion),
                    PART_LABELS[part],
                    *(format_metric(values[metric], 3) for metric in metrics),
                    format_metric(values["flagged_rate"] * 100, 1),
                ]
            )
    champion = next(r for r in task.results if r.name == task.champion)
    return [
        "## Classificação: o pedido vai atrasar?",
        "",
        "Alvo `is_late` (entregue depois da data prometida). PR-AUC é a métrica principal, porque "
        "a classe positiva é rara; a PR-AUC de um classificador aleatório é a própria taxa de "
        "atraso. F1, precisão e recall usam o limiar que maximiza o F1 na validação. Brier só "
        "para probabilidades.",
        "",
        *table_lines(header, ["---", "---", *["--:"] * (len(header) - 2)], rows),
        "",
        f"Campeão por PR-AUC na validação: `{task.champion}`, limiar "
        f"{format_metric(champion.threshold, 4)}. Registrado como `{CLASSIFIER_NAME}` versão "
        f"{task.registered_version}, alias `{CHAMPION_ALIAS}`.",
        "",
    ]


def regression_section(outcome: TrainingOutcome) -> list[str]:
    """Metrics of every regressor and baseline on validation and test."""
    task = outcome.regression
    rows = [
        [
            _label(result, task.champion),
            PART_LABELS[part],
            *(
                format_metric(getattr(result, part)[metric], 2)
                for metric in ("mae", "rmse", "bias")
            ),
        ]
        for result in task.results
        for part in ("validation", "test")
    ]
    return [
        "## Regressão: em quantos dias o pedido chega?",
        "",
        "Alvo `delivery_days` (da compra à entrega, em dias fracionários). Viés = média de "
        "(previsto − real): positivo significa prever mais dias do que a entrega levou.",
        "",
        *table_lines(
            ["método", "parte", "mae_days", "rmse_days", "bias_days"],
            ["---", "---", "--:", "--:", "--:"],
            rows,
        ),
        "",
        f"Campeão por MAE na validação: `{task.champion}`. Registrado como `{REGRESSOR_NAME}` "
        f"versão {task.registered_version}, alias `{CHAMPION_ALIAS}`.",
        "",
    ]


def calibration_section(outcome: TrainingOutcome) -> list[str]:
    """Reliability of the champion's probabilities on test."""
    rows = [
        [
            str(i + 1),
            format_metric(row.mean_predicted * 100, 1),
            format_metric(row.observed_rate * 100, 1),
        ]
        for i, row in enumerate(outcome.calibration.itertuples())
    ]
    return [
        "## Calibração do classificador campeão (teste)",
        "",
        *table_lines(["decil", "previsto_pct", "observado_pct"], ["--:", "--:", "--:"], rows),
        "",
    ]


def _format_feature_value(value: object) -> str:
    if isinstance(value, float):
        return format_metric(value, 2)
    return "-" if value is None or (isinstance(value, float) and math.isnan(value)) else str(value)


def shap_section(outcome: TrainingOutcome) -> list[str]:
    """Global importance and three individual orders."""
    explained = outcome.classification.extras["explained"]
    importance = outcome.explanation.importance.head(15)
    lines = [
        f"## Explicabilidade (SHAP, `{explained}`, teste)",
        "",
        "Média do |SHAP| numa amostra do teste, em log-odds de atraso.",
        "",
        *table_lines(
            ["feature", "mean_abs_shap"],
            ["---", "--:"],
            [[row.feature, format_metric(row.mean_abs_shap, 4)] for row in importance.itertuples()],
        ),
        "",
        "### Pedidos individuais",
        "",
        "As cinco features que mais pesaram em cada pedido (SHAP positivo empurra para o atraso).",
        "",
    ]
    for example in outcome.explanation.examples:
        lines += [
            f"**{example['label']}**: probabilidade prevista "
            f"{format_metric(example['score'] * 100, 1)}%, "
            f"{'atrasou' if example['is_late'] else 'chegou no prazo'}.",
            "",
            *table_lines(
                ["feature", "valor", "shap"],
                ["---", "--:", "--:"],
                [
                    [c["feature"], _format_feature_value(c["value"]), format_metric(c["shap"], 3)]
                    for c in example["contributions"]
                ],
            ),
            "",
        ]
    return lines


def write_report(outcome: TrainingOutcome, path: Path, run_date: date) -> Path:
    """Write the Markdown report of a training run."""
    lines = [
        "# Modelagem preditiva",
        "",
        f"Resultados de `make train` executado em {run_date.isoformat()} sobre os marts com os "
        "dados reais. Este arquivo é gerado: não edite à mão. Os números do README saem daqui. "
        "Alvos, features e colunas excluídas por vazamento: [model card](model_card.md).",
        "",
        *split_section(outcome),
        *classification_section(outcome),
        *regression_section(outcome),
        *calibration_section(outcome),
        *shap_section(outcome),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")
    return path

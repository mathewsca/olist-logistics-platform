"""Markdown report of the production replay, the source of the monitoring numbers in the README."""

from datetime import date
from pathlib import Path

import pandas as pd

from olist_platform.analytics.formatting import format_metric, table_lines
from olist_platform.monitoring.performance import (
    DRIFT_SHARE_TRIGGER,
    GATE_MIN_POSITIVES,
    GATE_MIN_RELATIVE_GAIN,
    LIFT_DROP_TRIGGER,
    MAE_RISE_TRIGGER,
    SLICE_MIN_POSITIVES,
)
from olist_platform.monitoring.registry import CLASSIFIER_NAME, EXPERIMENT_NAME, REGRESSOR_NAME
from olist_platform.monitoring.windows import LABEL_DELAY_MONTHS, MONITORED_MONTHS

REPORT_PATH = Path("docs/monitoramento.md")


def _pct(value: float | None) -> str:
    return format_metric(None if value is None else value * 100, 1)


def _gate(row) -> str:
    if row.challenger_version is None or pd.isna(row.challenger_version):
        return "-"
    verdict = "promovido" if row.gate_passed else "rejeitado"
    return f"v{row.challenger_version} {verdict}"


def months_section(runs: pd.DataFrame) -> list[str]:
    """One row per monitored month: who served it, how it did, drift and the decision."""
    rows = [
        [
            f"{row.month:%Y-%m}",
            f"{row.evaluated_at:%Y-%m-%d}",
            f"v{row.champion_version}",
            format_metric(row.orders, 0),
            format_metric(row.labelled, 0),
            _pct(row.late_rate),
            format_metric(row.pr_auc, 3),
            f"{format_metric(row.lift, 2)} ({format_metric(row.validation_lift, 2)})",
            _pct(row.recall),
            _pct(row.flagged_rate),
            f"{format_metric(row.mae, 2)} ({format_metric(row.validation_mae, 2)})",
            _pct(row.drift_share),
            "sim" if row.retrain_reasons else "não",
            _gate(row),
        ]
        for row in runs.itertuples()
    ]
    header = [
        "mês", "avaliado_em", "campeão", "pedidos", "com_rótulo", "atraso_pct", "pr_auc",
        "lift (validação)", "recall_pct", "sinalizados_pct", "mae_dias (validação)", "drift_pct",
        "retreino", "gate",
    ]  # fmt: skip
    return [
        "## Mês a mês",
        "",
        "Métricas do campeão que estava em produção no início de cada mês, sobre os pedidos "
        "daquele mês que já tinham sido entregues na data da avaliação. Lift = PR-AUC ÷ taxa de "
        "atraso (1 = aleatório); entre parênteses, o valor do mesmo modelo na sua validação.",
        "",
        *table_lines(header, ["---", "---", "---", *["--:"] * 10, "---"], rows),
        "",
    ]


def decisions_section(runs: pd.DataFrame) -> list[str]:
    """Why each retraining happened and what the quality gate said."""
    lines = ["## Retreinos e quality gate", ""]
    triggered = runs[runs["retrain_reasons"].notna()]
    if triggered.empty:
        return [*lines, "Nenhum gatilho de retreino disparou.", ""]
    for row in triggered.itertuples():
        lines.append(f"- **{row.month:%Y-%m}**: retreino por {row.retrain_reasons}.")
        if row.gate_detail:
            lines.append(f"  Gate: {_gate(row)}. {row.gate_detail}.")
    return [*lines, ""]


def slices_section(slices: pd.DataFrame, month) -> list[str]:
    """Region slices of one month."""
    month_slices = slices[slices["month"] == month]
    rows = [
        [
            row.region,
            format_metric(row.orders, 0),
            _pct(row.late_rate),
            _pct(row.flagged_rate),
            _pct(row.recall),
            format_metric(row.pr_auc, 3),
        ]
        for row in month_slices.itertuples()
    ]
    return [
        f"## Por região do cliente ({month:%Y-%m})",
        "",
        f"Recall e PR-AUC só com pelo menos {SLICE_MIN_POSITIVES} atrasos na região.",
        "",
        *table_lines(
            ["região", "pedidos", "atraso_pct", "sinalizados_pct", "recall_pct", "pr_auc"],
            ["---", "--:", "--:", "--:", "--:", "--:"],
            rows,
        ),
        "",
    ]


def write_report(runs: pd.DataFrame, slices: pd.DataFrame, path: Path, run_date: date) -> Path:
    """Write the Markdown report from the stored months."""
    if runs.empty:
        raise ValueError("No monitored months: run the simulation first")
    latest = runs.iloc[-1]
    first, last = MONITORED_MONTHS[0], MONITORED_MONTHS[-1]
    lines = [
        "# Monitoramento e retreino",
        "",
        f"Resultados de `make monitor` executado em {run_date.isoformat()} sobre os marts com os "
        "dados reais. Este arquivo é gerado: não edite à mão.",
        "",
        "## Como a simulação funciona",
        "",
        f"Os meses de {first} a {last} fazem o papel de produção, um de cada vez. O primeiro "
        f"campeão só viu o que era conhecido em {first.start_time:%Y-%m-%d}. Cada mês é avaliado "
        f"{LABEL_DELAY_MONTHS} mês depois de fechar, quando a maioria das entregas já chegou.",
        "",
        "Retreino quando qualquer gatilho dispara:",
        "",
        f"- *drift* (Evidently) em pelo menos {DRIFT_SHARE_TRIGGER:.0%} das features;",
        f"- lift abaixo de {1 - LIFT_DROP_TRIGGER:.0%} do lift da validação do campeão;",
        f"- MAE acima de {1 + MAE_RISE_TRIGGER:.0%} do MAE da validação do campeão.",
        "",
        "No gate, a receita de retreino ajustada com o que se sabia no início do mês enfrenta o "
        "par que serviu o mês. Ela passa se tiver, nesse mês, PR-AUC pelo menos "
        f"{GATE_MIN_RELATIVE_GAIN:.0%} acima do campeão e acima da regra da rota, MAE não pior e "
        f"pelo menos {GATE_MIN_POSITIVES} atrasos para comparar; então é reajustada com tudo o que "
        f"se sabe na avaliação e promovida. Os modelos ficam em `{CLASSIFIER_NAME}` e "
        f"`{REGRESSOR_NAME}`, separados dos que a API serve.",
        "",
        *months_section(runs),
        *decisions_section(runs),
        *slices_section(slices, latest["month"]),
        "## Relatório de drift",
        "",
        "O relatório do Evidently de cada mês (features servidas × referência do treino do "
        f"campeão) fica no MLflow, no run `evaluate-AAAA-MM` do experimento `{EXPERIMENT_NAME}`. "
        "Ficam fora da fração de drift `purchase_month` (um único mês sempre difere de uma "
        "referência de um ano inteiro) e o histórico do vendedor (o snapshot servido para de "
        "crescer, então o drift dele mediria só a idade do snapshot).",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")
    return path

"""Run the compiled dbt analyses against the warehouse and write their results as Markdown."""

import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import psycopg

from olist_platform.analytics.formatting import format_value
from olist_platform.analytics.quality import load_data_quality

DBT_PROJECT_NAME = "olist"
REPORT_PATH = Path("docs/analises.md")


@dataclass(frozen=True)
class Analysis:
    """One file in ``dbt/analyses/`` and how it is presented in the report."""

    name: str
    title: str
    description: str


ANALYSES = (
    Analysis(
        "monthly_late_rate",
        "Taxa de atraso por mês de compra",
        "Entregas, % entregue depois da data prometida, atraso médio dos atrasados e prazo "
        "mediano.",
    ),
    Analysis(
        "monthly_revenue",
        "Receita entregue por mês de compra",
        "Itens + frete dos pedidos entregues; `late_revenue_pct` é a parte dessa receita que "
        "chegou com atraso.",
    ),
    Analysis(
        "late_rate_by_purchase_weekday",
        "Demanda e atraso por dia da semana da compra",
        "Volume, atraso e dias da compra ao envio à transportadora (`seller_handling_days`).",
    ),
    Analysis(
        "route_state_pairs",
        "Rotas UF → UF mais movimentadas",
        "As 20 rotas com mais entregas (mínimo de 300), com atraso, distância, prazo prometido "
        "e real.",
    ),
    Analysis(
        "late_rate_by_category",
        "Atraso por categoria de produto",
        "Categorias com pelo menos 1.000 entregas, da maior para a menor taxa de atraso.",
    ),
    Analysis(
        "late_rate_by_freight",
        "Atraso por faixa de frete (R$)",
        "Frete total do pedido.",
    ),
    Analysis(
        "late_rate_by_distance",
        "Atraso por faixa de distância vendedor → cliente (km)",
        "Distância em linha reta; `unknown` = prefixo de CEP sem geolocalização.",
    ),
    Analysis(
        "freight_share_by_distance",
        "Peso do frete por faixa de distância (km)",
        "Mediana de frete ÷ valor dos itens, em %.",
    ),
    Analysis(
        "late_rate_by_payment_type",
        "Pagamento, aprovação e atraso",
        "Forma de pagamento de maior valor no pedido; horas da compra à aprovação (mediana).",
    ),
    Analysis(
        "late_vs_review",
        "Avaliação por faixa de atraso",
        "Nota média e % de notas 1–2 entre as entregas avaliadas.",
    ),
    Analysis(
        "review_comments_by_score",
        "O que dizem os comentários das avaliações",
        "Avaliações com comentário; `mentions_delivery_pct` = o texto cita entrega, prazo, "
        "atraso, recebimento, correios ou transportadora.",
    ),
    Analysis(
        "seller_late_vs_review",
        "Vendedores: taxa de atraso × nota",
        "Vendedores com pelo menos 30 entregas, por faixa da sua taxa de atraso (%).",
    ),
    Analysis(
        "estimate_bias",
        "Folga do prazo prometido por UF do cliente",
        "Folga = dias prometidos − dias reais. A primeira linha (`all`) é o total.",
    ),
    Analysis(
        "repurchase_after_first_delivery",
        "Recompra em 180 dias conforme a primeira entrega",
        "Clientes (`customer_unique_id`) cuja primeira compra entregue tem 180 dias de janela "
        "observada.",
    ),
)


@dataclass(frozen=True)
class AnalysisResult:
    """Columns and rows returned by one analysis."""

    analysis: Analysis
    columns: list[str]
    rows: list[tuple]


def compiled_analyses_dir(dbt_project_dir: Path) -> Path:
    """Where ``dbt compile`` writes the analyses (honours ``DBT_TARGET_PATH``, like dbt)."""
    target = os.environ.get("DBT_TARGET_PATH", "target")
    return dbt_project_dir / target / "compiled" / DBT_PROJECT_NAME / "analyses"


def run_analyses(conn: psycopg.Connection, compiled_dir: Path) -> list[AnalysisResult]:
    """Execute every analysis, in report order."""
    results = []
    for analysis in ANALYSES:
        sql = (compiled_dir / f"{analysis.name}.sql").read_text(encoding="utf-8")
        cursor = conn.execute(sql)
        columns = [column.name for column in cursor.description]
        results.append(AnalysisResult(analysis, columns, cursor.fetchall()))
    return results


def is_numeric_column(rows: list[tuple], index: int) -> bool:
    """Whether the column holds numbers, so it is right-aligned."""
    values = [row[index] for row in rows if row[index] is not None]
    return bool(values) and all(
        isinstance(v, int | float | Decimal) and not isinstance(v, bool) for v in values
    )


def markdown_table(columns: list[str], rows: list[tuple]) -> str:
    """Rows as a GitHub Markdown table."""
    header = "| " + " | ".join(columns) + " |"
    separator = (
        "|"
        + "|".join("--:" if is_numeric_column(rows, i) else "---" for i in range(len(columns)))
        + "|"
    )
    body = ["| " + " | ".join(format_value(value) for value in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def quality_section(quality: pd.DataFrame) -> list[str]:
    """Known source issues with the violations counted by their dbt tests."""
    rows = [
        (row.issue, f"`{row.model}`", None if pd.isna(row.violations) else int(row.violations),
         row.treatment)
        for row in quality.itertuples()
    ]  # fmt: skip
    return [
        "",
        "## Qualidade dos dados",
        "",
        "Anomalias conhecidas da fonte. Cada uma tem um teste dbt com severidade `warn`, que conta "
        "as violações e guarda as linhas no schema `audit`; problema e tratamento vêm da seed "
        "`dbt/seeds/data_issues.csv`.",
        "",
        markdown_table(["problema", "modelo", "violações", "tratamento"], rows),
    ]


def render_report(
    results: list[AnalysisResult], generated_on: date, quality: pd.DataFrame | None = None
) -> str:
    """Full Markdown document with one section per analysis, then the data quality."""
    lines = [
        "# Análises de logística",
        "",
        f"Resultados das consultas em `dbt/analyses/`, executadas em {generated_on.isoformat()} "
        "sobre os marts com os dados reais. Este arquivo é gerado por `make analyses`: não edite à "
        "mão. Os números do README saem daqui.",
        "",
        "População: `fct_deliveries` (pedidos entregues com data de entrega). Atraso = entregue "
        "depois da data prometida pela Olist (datas de calendário). Percentuais em `_pct`; dias "
        "em `_days`.",
    ]
    for result in results:
        lines += [
            "",
            f"## {result.analysis.title}",
            "",
            f"{result.analysis.description} Consulta: `dbt/analyses/{result.analysis.name}.sql`.",
            "",
            markdown_table(result.columns, result.rows),
        ]
    if quality is not None and not quality.empty:
        lines += quality_section(quality)
    return "\n".join(lines) + "\n"


def write_report(
    conn: psycopg.Connection, dbt_project_dir: Path, output: Path, generated_on: date
) -> list[AnalysisResult]:
    """Run the analyses compiled for ``dbt_project_dir`` and write the report to ``output``."""
    results = run_analyses(conn, compiled_analyses_dir(dbt_project_dir))
    report = render_report(results, generated_on, load_data_quality(conn))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8", newline="\n")
    return results

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .client import TPCUClient
from .config import Settings
from .parser import parse_absence
from .reporting import (
    generate_absence_chart,
    generate_period_table_image,
    sort_absence_records,
)


@dataclass(frozen=True)
class QueryResult:
    records: list
    chart_path: str
    table_path: str
    debug_path: str


def ensure_output_layout(settings: Settings) -> None:
    for output_path in [
        settings.debug_output_path,
        settings.chart_output_path,
        settings.table_output_path,
    ]:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)


def run_absence_query(
    *,
    client: TPCUClient,
    settings: Settings,
    start_date: date,
    end_date: date,
) -> QueryResult:
    html = client.get_absence_html(start_date=start_date, end_date=end_date)

    debug_path = settings.debug_output_path
    Path(debug_path).write_text(html, encoding="utf-8")

    if "學生個人缺曠請假明細表" not in html:
        raise RuntimeError(f"查詢失敗：回應不是缺曠表，已輸出 {debug_path}")

    records = sort_absence_records(parse_absence(html))
    chart_path = generate_absence_chart(
        records,
        start_date=start_date,
        end_date=end_date,
        output_path=settings.chart_output_path,
        title="缺曠 / 請假總覽",
    )
    table_path = generate_period_table_image(
        records,
        start_date=start_date,
        end_date=end_date,
        output_path=settings.table_output_path,
        title="節次明細表",
    )

    return QueryResult(
        records=records,
        chart_path=chart_path,
        table_path=table_path,
        debug_path=debug_path,
    )

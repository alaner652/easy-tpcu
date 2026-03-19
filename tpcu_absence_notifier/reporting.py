from collections import Counter
from datetime import date, datetime
from pathlib import Path
import re

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.colors import to_hex, to_rgb
from matplotlib.patches import FancyBboxPatch

from .models import AbsenceRecord

CHART_OUTPUT = "outputs/charts/absence_chart.png"
TABLE_OUTPUT = "outputs/charts/absence_period_table.png"
CHART_PALETTE = [
    "#2563eb",
    "#0f766e",
    "#ea580c",
    "#dc2626",
    "#7c3aed",
    "#0891b2",
    "#ca8a04",
    "#db2777",
]

plt.rcParams["font.sans-serif"] = [
    "PingFang TC",
    "Microsoft JhengHei",
    "Noto Sans CJK TC",
    "Heiti TC",
    "Arial Unicode MS",
    "SimHei",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False

DATE_PATTERN = re.compile(r"(\d{2,3})/(\d{1,2})/(\d{1,2})")


def parse_roc_date(value: str) -> date | None:
    match = DATE_PATTERN.search(value.strip())
    if not match:
        return None

    try:
        year_str, month_str, day_str = match.groups()
        return date(int(year_str) + 1911, int(month_str), int(day_str))
    except (TypeError, ValueError):
        return None


def format_record_date(value: str, fmt: str = "%Y-%m-%d") -> str:
    parsed = parse_roc_date(value)
    if parsed is None:
        return value
    return parsed.strftime(fmt)


def format_query_window(start_date: date, end_date: date) -> str:
    if start_date == end_date:
        return start_date.isoformat()
    return f"{start_date.isoformat()} ~ {end_date.isoformat()}"


def unique_absence_days(records: list[AbsenceRecord]) -> int:
    return len({record.date for record in records})


def summarize_type_totals(records: list[AbsenceRecord]) -> Counter[str]:
    return Counter(record.absence_type for record in records)


def format_type_summary(records: list[AbsenceRecord]) -> str:
    type_totals = summarize_type_totals(records)
    if not type_totals:
        return "無缺曠 / 請假紀錄"
    return " / ".join(f"{absence_type} {count}" for absence_type, count in type_totals.items())


def summarize_absence(records: list[AbsenceRecord]) -> tuple[list[str], list[str], dict[tuple[str, str], int]]:
    date_labels: set[str] = set()
    type_labels: list[str] = []
    counts: dict[tuple[str, str], int] = {}

    for record in records:
        date_labels.add(record.date)
        if record.absence_type not in type_labels:
            type_labels.append(record.absence_type)

        key = (record.date, record.absence_type)
        counts[key] = counts.get(key, 0) + 1

    sorted_dates = sorted(date_labels, key=lambda value: parse_roc_date(value) or date.min)
    return sorted_dates, type_labels, counts


def period_sort_key(label: str) -> tuple[int, int, str]:
    special_order = {
        "朝會": -20,
        "晨會": -19,
        "早自習": -18,
        "午休": 98,
        "晚自習": 99,
    }
    digits = "".join(ch for ch in label if ch.isdigit())

    if label in special_order:
        return (0, special_order[label], label)
    if digits:
        return (1, int(digits), label)
    return (2, 0, label)


def build_period_table(
    records: list[AbsenceRecord],
) -> tuple[list[str], list[str], dict[tuple[str, str], str], Counter[str]]:
    date_labels: set[str] = set()
    period_labels: set[str] = set()
    cell_types: dict[tuple[str, str], set[str]] = {}
    period_totals: Counter[str] = Counter()

    for record in records:
        date_labels.add(record.date)
        period_labels.add(record.period)
        period_totals[record.period] += 1

        key = (record.date, record.period)
        cell_types.setdefault(key, set()).add(record.absence_type)

    sorted_dates = sorted(
        date_labels,
        key=lambda value: parse_roc_date(value) or date.min,
        reverse=True,
    )
    cell_map = {
        key: " / ".join(sorted(values))
        for key, values in cell_types.items()
    }

    return sorted_dates, sorted(period_labels, key=period_sort_key), cell_map, period_totals


def format_period_label(period: str) -> str:
    if period.startswith("第") or period.endswith("節"):
        return period
    if any(ch.isdigit() for ch in period):
        return f"第{period}節"
    return period


def type_color_map(type_labels: list[str]) -> dict[str, str]:
    return {
        absence_type: CHART_PALETTE[idx % len(CHART_PALETTE)]
        for idx, absence_type in enumerate(type_labels)
    }


def resolve_cell_color(cell_value: str, colors: dict[str, str]) -> str:
    if not cell_value:
        return "#ffffff"
    if cell_value in colors:
        return colors[cell_value]
    return "#e0f2fe"


def soften_color(color: str, amount: float = 0.78) -> str:
    red, green, blue = to_rgb(color)
    blended = tuple(channel + (1 - channel) * amount for channel in (red, green, blue))
    return to_hex(blended)


def generate_absence_chart(
    records: list[AbsenceRecord],
    start_date: date,
    end_date: date,
    output_path: str = CHART_OUTPUT,
    title: str | None = None,
) -> str:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    chart_title = title or "缺曠 / 請假總覽"
    query_window = format_query_window(start_date, end_date)
    fig, ax = plt.subplots(figsize=(10, 5.8), dpi=180, layout="constrained")
    fig.patch.set_facecolor("#f4f7fb")
    ax.set_facecolor("#ffffff")

    if not records:
        ax.axis("off")
        ax.text(
            0.04,
            0.62,
            "本次查詢沒有缺曠 / 請假紀錄",
            ha="left",
            va="center",
            fontsize=20,
            fontweight="bold",
            color="#0f172a",
            transform=ax.transAxes,
        )
        ax.text(
            0.04,
            0.45,
            f"查詢區間 {query_window}",
            ha="left",
            va="center",
            fontsize=12,
            color="#334155",
            transform=ax.transAxes,
        )
        ax.text(
            0.04,
            0.33,
            "仍會發送通知，方便確認查詢與排程都正常。",
            ha="left",
            va="center",
            fontsize=11,
            color="#475569",
            transform=ax.transAxes,
        )
        ax.text(
            0.04,
            0.78,
            f"TPCU {chart_title}",
            ha="left",
            va="center",
            fontsize=13,
            fontweight="bold",
            color="#2563eb",
            transform=ax.transAxes,
        )
        fig.savefig(output_file, bbox_inches="tight", pad_inches=0.18)
        plt.close(fig)
        return str(output_file)

    date_labels, type_labels, counts = summarize_absence(records)
    type_totals = summarize_type_totals(records)
    positions = list(range(len(date_labels)))
    bottoms = [0] * len(date_labels)
    totals_by_date = [0] * len(date_labels)
    width = max(9.5, len(date_labels) * 0.9)
    fig.set_size_inches(width, 5.8)
    colors = type_color_map(type_labels)
    display_labels = [format_record_date(label, "%m/%d") for label in date_labels]

    for absence_type in type_labels:
        values = [counts.get((date_label, absence_type), 0) for date_label in date_labels]
        totals_by_date = [total + value for total, value in zip(totals_by_date, values)]
        ax.bar(
            positions,
            values,
            bottom=bottoms,
            label=f"{absence_type} ({type_totals[absence_type]})",
            color=colors[absence_type],
            edgecolor="#ffffff",
            linewidth=1.0,
        )
        bottoms = [bottom + value for bottom, value in zip(bottoms, values)]

    for pos, total in zip(positions, totals_by_date):
        if total > 0:
            ax.text(pos, total + 0.05, str(total), ha="center", va="bottom", fontsize=9, color="#0f172a")

    summary_text = format_type_summary(records)
    max_total = max(totals_by_date)

    ax.set_title(chart_title, fontsize=16, fontweight="bold", pad=16)
    ax.text(
        0.0,
        1.04,
        f"{query_window}   |   {len(records)} 節 / {unique_absence_days(records)} 天   |   {summary_text}",
        transform=ax.transAxes,
        fontsize=10,
        color="#334155",
    )
    ax.set_ylabel("節次")
    ax.set_xticks(positions)
    ax.set_xticklabels(display_labels, rotation=0)
    ax.set_ylim(0, max(3, max_total * 1.25))
    ax.grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.35)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    ax.legend(loc="upper left", frameon=False, ncols=min(4, len(type_labels)))

    fig.savefig(output_file, bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)
    return str(output_file)


def generate_period_table_image(
    records: list[AbsenceRecord],
    start_date: date,
    end_date: date,
    output_path: str = TABLE_OUTPUT,
    title: str | None = None,
) -> str:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    table_title = title or "節次明細表"
    query_window = format_query_window(start_date, end_date)
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=180, layout="constrained")
    fig.patch.set_facecolor("#f4f7fb")
    ax.axis("off")

    if not records:
        ax.text(
            0.04,
            0.60,
            "沒有可顯示的節次明細",
            ha="left",
            va="center",
            fontsize=20,
            fontweight="bold",
            color="#0f172a",
            transform=ax.transAxes,
        )
        ax.text(
            0.04,
            0.44,
            f"查詢區間 {query_window} 沒有缺曠 / 請假紀錄",
            ha="left",
            va="center",
            fontsize=12,
            color="#475569",
            transform=ax.transAxes,
        )
        ax.text(
            0.04,
            0.76,
            f"TPCU {table_title}",
            ha="left",
            va="center",
            fontsize=13,
            fontweight="bold",
            color="#0f766e",
            transform=ax.transAxes,
        )
        fig.savefig(output_file, bbox_inches="tight", pad_inches=0.18)
        plt.close(fig)
        return str(output_file)

    date_labels, period_labels, cell_map, period_totals = build_period_table(records)
    type_totals = summarize_type_totals(records)
    type_labels = list(type_totals.keys())
    colors = {absence_type: soften_color(color) for absence_type, color in type_color_map(type_labels).items()}

    col_labels = ["日期", *[format_period_label(period) for period in period_labels]]
    cell_text: list[list[str]] = []
    cell_colors: list[list[str]] = []

    for row_index, raw_date in enumerate(date_labels):
        base_row_color = "#ffffff" if row_index % 2 == 0 else "#f8fafc"
        row_text = [format_record_date(raw_date, "%m/%d")]
        row_colors = ["#f1f5f9" if row_index % 2 == 0 else "#e2e8f0"]
        for period in period_labels:
            cell_value = cell_map.get((raw_date, period), "")
            row_text.append(cell_value)
            row_colors.append(resolve_cell_color(cell_value, colors) if cell_value else base_row_color)
        cell_text.append(row_text)
        cell_colors.append(row_colors)

    totals_row = ["總計", *[str(period_totals.get(period, 0)) for period in period_labels]]
    totals_colors = ["#dbeafe", *["#eff6ff" for _ in period_labels]]
    cell_text.append(totals_row)
    cell_colors.append(totals_colors)

    width = max(10.5, 3.2 + len(period_labels) * 1.02)
    height = max(5.6, 2.5 + len(cell_text) * 0.52)
    fig.set_size_inches(width, height)
    fig.clear()
    fig.patch.set_facecolor("#f4f7fb")
    grid = fig.add_gridspec(2, 1, height_ratios=[0.2, 0.8])
    header_ax = fig.add_subplot(grid[0])
    table_ax = fig.add_subplot(grid[1])
    header_ax.axis("off")
    table_ax.axis("off")

    header_card = FancyBboxPatch(
        (0.0, 0.08),
        1.0,
        0.84,
        boxstyle="round,pad=0.02,rounding_size=0.05",
        facecolor="#ffffff",
        edgecolor="#e2e8f0",
        linewidth=0.8,
        transform=header_ax.transAxes,
    )
    header_ax.add_patch(header_card)
    header_ax.text(
        0.04,
        0.64,
        table_title,
        fontsize=17,
        fontweight="bold",
        color="#0f172a",
        transform=header_ax.transAxes,
    )
    header_ax.text(
        0.04,
        0.39,
        f"查詢區間 {query_window}",
        fontsize=11,
        color="#334155",
        transform=header_ax.transAxes,
    )
    header_ax.text(
        0.04,
        0.18,
        f"共 {len(records)} 節 / {unique_absence_days(records)} 天   |   最新日期在上   |   空白表示該節次無紀錄",
        fontsize=10,
        color="#475569",
        transform=header_ax.transAxes,
    )

    table = table_ax.table(
        cellText=cell_text,
        cellColours=cell_colors,
        colLabels=col_labels,
        colColours=["#e2e8f0", *["#eef2ff" for _ in period_labels]],
        cellLoc="center",
        loc="center",
        bbox=[0.01, 0.0, 0.98, 1.0],
    )

    table.auto_set_font_size(False)
    table.set_fontsize(9.2)
    table.scale(1, 1.55)
    table.auto_set_column_width(col=list(range(len(col_labels))))

    totals_row_index = len(cell_text)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#e2e8f0")
        cell.set_linewidth(0.75)
        if row == 0:
            cell.set_text_props(weight="bold", color="#0f172a")
            cell.set_height(cell.get_height() * 1.1)
        elif row == totals_row_index:
            cell.set_text_props(weight="bold", color="#0f172a")
        elif col == 0:
            cell.set_text_props(weight="bold", color="#0f172a")
        elif cell.get_text().get_text():
            cell.set_text_props(weight="bold", color="#0f172a")
        else:
            cell.set_text_props(color="#94a3b8")

    fig.savefig(output_file, bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)
    return str(output_file)


def sort_absence_records(records: list[AbsenceRecord]) -> list[AbsenceRecord]:
    def sort_key(record: AbsenceRecord) -> tuple[datetime, tuple[int, int, str], str]:
        parsed_date = parse_roc_date(record.date)
        sortable_date = datetime.combine(parsed_date, datetime.min.time()) if parsed_date else datetime.min
        return sortable_date, period_sort_key(record.period), record.absence_type

    return sorted(records, key=sort_key)

from argparse import ArgumentParser, Namespace
from datetime import date, datetime, timedelta
from pathlib import Path

from tpcu_absence_notifier.client import TPCUClient
from tpcu_absence_notifier.config import load_settings
from tpcu_absence_notifier.discord_notifier import send_discord
from tpcu_absence_notifier.parser import parse_absence
from tpcu_absence_notifier.reporting import (
    format_period_label,
    format_query_window,
    format_type_summary,
    generate_absence_chart,
    generate_period_table_image,
    sort_absence_records,
    unique_absence_days,
)

DEFAULT_LOOKBACK_DAYS = 30


def ensure_output_layout(settings) -> None:
    for output_path in [
        settings.debug_output_path,
        settings.chart_output_path,
        settings.table_output_path,
    ]:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)


def parse_cli_date(raw: str) -> date:
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"日期格式錯誤：{raw}，請使用 YYYY-MM-DD") from exc


def positive_days(raw: str) -> int:
    value = int(raw)
    if value <= 0:
        raise ValueError("--days 必須大於 0")
    return value


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="查詢 TPCU 缺曠 / 請假紀錄並透過 Discord 通知")
    parser.add_argument("--date", type=parse_cli_date, help="查詢單日資料，格式 YYYY-MM-DD")
    parser.add_argument("--start-date", type=parse_cli_date, help="查詢起始日，格式 YYYY-MM-DD")
    parser.add_argument("--end-date", type=parse_cli_date, help="查詢結束日，格式 YYYY-MM-DD")
    parser.add_argument(
        "--days",
        type=positive_days,
        default=DEFAULT_LOOKBACK_DAYS,
        help=f"未指定日期時，往前查詢的天數，預設 {DEFAULT_LOOKBACK_DAYS} 天",
    )
    return parser


def resolve_query_window(parser: ArgumentParser, args: Namespace) -> tuple[date, date]:
    if args.date and (args.start_date or args.end_date):
        parser.error("--date 不能和 --start-date / --end-date 同時使用")

    if args.date:
        return args.date, args.date

    if args.start_date or args.end_date:
        start_date = args.start_date or args.end_date
        end_date = args.end_date or args.start_date
    else:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=args.days - 1)

    if start_date > end_date:
        parser.error("起始日期不能晚於結束日期")

    return start_date, end_date


def build_discord_fields(records, start_date: date, end_date: date) -> list[dict[str, object]]:
    fields: list[dict[str, object]] = [
        {"name": "查詢區間", "value": format_query_window(start_date, end_date), "inline": False},
    ]

    if not records:
        fields.append({"name": "查詢結果", "value": "本次區間沒有缺曠 / 請假紀錄", "inline": False})
        return fields

    fields.append(
        {
            "name": "統計摘要",
            "value": f"{len(records)} 節 / {unique_absence_days(records)} 天",
            "inline": True,
        }
    )
    fields.append({"name": "類型統計", "value": format_type_summary(records), "inline": False})

    return fields


def build_discord_description(records) -> str:
    if not records:
        return "本次查詢完成，無缺曠 / 請假紀錄。"
    return f"本次查詢完成，共 {len(records)} 節，分布於 {unique_absence_days(records)} 天。詳情請見附圖。"


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    start_date, end_date = resolve_query_window(parser, args)
    settings = load_settings()
    ensure_output_layout(settings)
    client = TPCUClient(settings)

    client.login()
    print("登入成功")
    print(f"查詢區間：{format_query_window(start_date, end_date)}")

    html = client.get_absence_html(start_date=start_date, end_date=end_date)

    with open(settings.debug_output_path, "w", encoding="utf-8") as file_handle:
        file_handle.write(html)

    if "學生個人缺曠請假明細表" not in html:
        raise RuntimeError(f"查詢失敗：回應不是缺曠表，已輸出 {settings.debug_output_path}")

    records = sort_absence_records(parse_absence(html))

    print(f"找到 {len(records)} 筆節次紀錄")
    for record in records[:10]:
        print(f"{record.date} {format_period_label(record.period)} - {record.absence_type}")

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
    print(f"已輸出圖表：{chart_path}")
    print(f"已輸出節次表格：{table_path}")

    send_discord(
        settings.discord_webhook,
        title="TPCU 缺曠 / 請假查詢",
        description=build_discord_description(records),
        fields=build_discord_fields(records, start_date, end_date),
        image_paths=[chart_path, table_path],
    )
    print(f"Discord 已通知：{format_query_window(start_date, end_date)}")


if __name__ == "__main__":
    main()

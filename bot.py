from argparse import ArgumentParser, Namespace
from datetime import date, datetime, timedelta

from tpcu_absence_notifier.auto_leave import run_auto_leave
from tpcu_absence_notifier.client import TPCUClient
from tpcu_absence_notifier.config import load_settings
from tpcu_absence_notifier.discord_notifier import send_discord
from tpcu_absence_notifier.reporting import format_period_label, format_query_window
from tpcu_absence_notifier.summary import build_discord_description, build_discord_fields
from tpcu_absence_notifier.workflow import ensure_output_layout, run_absence_query

DEFAULT_LOOKBACK_DAYS = 30


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
    parser.add_argument(
        "--auto-leave",
        action="store_true",
        help="符合條件時自動送出請假（需先設定 .env 的請假參數）",
    )
    parser.add_argument(
        "--auto-leave-dry-run",
        action="store_true",
        help="僅列出將送出的請假，不實際送出",
    )
    parser.add_argument(
        "--auto-leave-force",
        action="store_true",
        help="忽略去重紀錄，強制送出自動請假",
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

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    start_date, end_date = resolve_query_window(parser, args)
    auto_leave = args.auto_leave or args.auto_leave_dry_run
    dry_run = args.auto_leave_dry_run
    force_leave = args.auto_leave_force
    settings = load_settings()
    ensure_output_layout(settings)
    client = TPCUClient(settings)

    client.login()
    print("登入成功")
    print(f"查詢區間：{format_query_window(start_date, end_date)}")

    result = run_absence_query(
        client=client,
        settings=settings,
        start_date=start_date,
        end_date=end_date,
    )
    records = result.records

    print(f"找到 {len(records)} 筆節次紀錄")
    for record in records[:10]:
        print(f"{record.date} {format_period_label(record.period)} - {record.absence_type}")

    if auto_leave:
        run_auto_leave(
            client=client,
            records=records,
            settings=settings,
            dry_run=dry_run,
            force=force_leave,
            logger=print,
        )

    chart_path = result.chart_path
    table_path = result.table_path
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

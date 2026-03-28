from __future__ import annotations

from datetime import date

from .reporting import format_query_window, format_type_summary, unique_absence_days


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

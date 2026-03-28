from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
import re
from typing import Callable

from .client import TPCUClient, normalize_period_key
from .reporting import parse_roc_date

LEAVE_HISTORY_VERSION = 1


@dataclass(frozen=True)
class AutoLeaveResult:
    date: date
    periods: list[str]
    status: str
    message: str
    response_path: Path


def build_auto_leave_targets(records, keywords: tuple[str, ...]) -> dict[date, set[str]]:
    targets: dict[date, set[str]] = defaultdict(set)
    for record in records:
        if not any(keyword in record.absence_type for keyword in keywords):
            continue
        parsed_date = parse_roc_date(record.date)
        if parsed_date is None:
            continue
        targets[parsed_date].add(normalize_period_key(record.period))
    return targets


def load_leave_history(history_path: Path) -> list[dict[str, object]]:
    if not history_path.exists():
        return []
    try:
        payload = json.loads(history_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        entries = payload.get("entries", [])
        if isinstance(entries, list):
            return entries
        return []
    if isinstance(payload, list):
        return payload
    return []


def save_leave_history(history_path: Path, entries: list[dict[str, object]]) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": LEAVE_HISTORY_VERSION, "entries": entries}
    history_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_history_index(entries: list[dict[str, object]]) -> dict[str, dict[str, set[str]]]:
    index: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for entry in entries:
        date_key = str(entry.get("date", "")).strip()
        leave_id = str(entry.get("leave_id", "")).strip()
        status = str(entry.get("status", "")).strip()
        if status not in {"success", "unknown"}:
            continue
        periods = entry.get("periods", [])
        if not date_key or not leave_id or not isinstance(periods, list):
            continue
        index[date_key][leave_id].update(str(p).strip() for p in periods if str(p).strip())
    return index


def refresh_leave_history_statuses(entries: list[dict[str, object]]) -> bool:
    changed = False
    for entry in entries:
        if entry.get("status") != "unknown":
            continue
        response_path = entry.get("response_path")
        if not response_path:
            continue
        path = Path(str(response_path))
        if not path.exists():
            continue
        try:
            html = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        status, message = classify_leave_response(html)
        if status != entry.get("status") or message != entry.get("message"):
            entry["status"] = status
            entry["message"] = message
            entry["rechecked_at"] = datetime.now().isoformat(timespec="seconds")
            changed = True
    return changed


def extract_alert_message(html: str) -> str | None:
    match = re.search(r"alert\\((['\"])(.*?)\\1\\)", html, re.DOTALL)
    if not match:
        return None
    return match.group(2).strip()


def classify_leave_response(html: str) -> tuple[str, str]:
    alert_message = extract_alert_message(html)
    if alert_message:
        failure_keywords = (
            "失敗",
            "錯誤",
            "請選取",
            "請輸入",
            "請選擇",
            "不得",
            "必須",
            "重複",
            "未到",
            "附件",
            "格式不正確",
        )
        success_keywords = (
            "完成",
            "成功",
            "已送出",
            "存檔",
            "申請完成",
            "請假完成",
            "准假",
            "核假",
            "請假天數",
            "線上准假",
        )
        if any(keyword in alert_message for keyword in failure_keywords):
            return "failure", alert_message
        if any(keyword in alert_message for keyword in success_keywords):
            return "success", alert_message
        return "unknown", alert_message

    if "學生網路請假作業" in html:
        return "unknown", "回應仍是請假頁面，未偵測到 alert 訊息"
    return "unknown", "未偵測到可判斷的回應訊息"


def run_auto_leave(
    *,
    client: TPCUClient,
    records,
    settings,
    dry_run: bool,
    force: bool,
    logger: Callable[[str], None] | None = None,
) -> list[AutoLeaveResult]:
    log = logger or (lambda _msg: None)

    targets = build_auto_leave_targets(records, settings.leave_auto_types)
    if not targets:
        log("自動請假：未找到符合條件的缺曠紀錄")
        return []

    period_order_keys = {normalize_period_key(label) for label in settings.leave_period_order}
    if not period_order_keys:
        raise RuntimeError("自動請假需要設定 .env：TPCU_LEAVE_PERIODS")

    history_path = Path(settings.leave_history_file)
    history_entries = load_leave_history(history_path)
    if refresh_leave_history_statuses(history_entries):
        save_leave_history(history_path, history_entries)
    history_index = build_history_index(history_entries)

    results: list[AutoLeaveResult] = []
    for target_date, periods in sorted(targets.items()):
        missing = sorted(periods - period_order_keys)
        if missing:
            raise RuntimeError(
                f"自動請假失敗：查詢到未知節次 {missing}，請更新 TPCU_LEAVE_PERIODS"
            )

        date_key = target_date.isoformat()
        leave_id = settings.leave_type_id or ""
        already_sent = set()
        if not force and leave_id:
            already_sent = history_index.get(date_key, {}).get(leave_id, set())

        pending_periods = set(periods) - already_sent
        if not pending_periods:
            log(f"自動請假：{date_key} 已送出過，略過")
            continue

        if dry_run:
            log(f"自動請假（乾跑）：{date_key} -> {sorted(pending_periods)}")
            continue

        response_html = client.submit_leave(target_date, pending_periods)
        debug_path = Path(settings.output_dir) / "debug" / f"leave_{date_key}.html"
        debug_path.write_text(response_html, encoding="utf-8")
        status, message = classify_leave_response(response_html)
        log(
            f"自動請假已送出：{date_key} -> {sorted(pending_periods)}，"
            f"狀態={status}，訊息={message}，回應已輸出 {debug_path}"
        )
        history_entries.append(
            {
                "date": date_key,
                "leave_id": leave_id,
                "periods": sorted(pending_periods),
                "status": status,
                "message": message,
                "response_path": str(debug_path),
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
        )
        save_leave_history(history_path, history_entries)
        results.append(
            AutoLeaveResult(
                date=target_date,
                periods=sorted(pending_periods),
                status=status,
                message=message,
                response_path=debug_path,
            )
        )

    return results

from datetime import date

import requests
import urllib3

from .config import Settings

urllib3.disable_warnings()


def roc_date_parts(dt: date) -> tuple[str, str, str, str]:
    roc_year = str(dt.year - 1911)
    month = dt.strftime("%m")
    day = dt.strftime("%d")
    compact = f"{roc_year}{month}{day}"
    return roc_year, month, day, compact


def normalize_period_key(label: str) -> str:
    return label.replace("第", "").replace("節", "").strip()


def build_lea_value(
    compact_date: str,
    period_order: tuple[str, ...],
    target_periods: set[str],
    leave_type_id: str,
) -> str:
    values: list[str] = []
    for label in period_order:
        key = normalize_period_key(label)
        values.append(leave_type_id if key in target_periods else "0")
    return f"{compact_date}%{'%'.join(values)}%"


class TPCUClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()

    def login(self) -> None:
        payload = {
            "hid_type": "S",
            "uid": self.settings.uid,
            "pwd": self.settings.pwd,
            "err": "N",
            "fncid": "",
            "ls_chochk": "N",
        }

        resp = self.session.post(self.settings.login_url, data=payload, verify=False, timeout=15)
        resp.raise_for_status()

        if "無此帳號或密碼" in resp.text:
            raise RuntimeError("登入失敗：帳號或密碼錯誤")

        if "JSESSIONID" not in self.session.cookies.get_dict():
            raise RuntimeError("登入失敗：未取得 JSESSIONID")

    def get_absence_html(self, start_date: date, end_date: date) -> str:
        if start_date > end_date:
            raise ValueError("start_date 不能晚於 end_date")

        s_year, s_month, s_day, sdate = roc_date_parts(start_date)
        e_year, e_month, e_day, edate = roc_date_parts(end_date)

        payload = {
            "yms": self.settings.school_year_semester,
            "leave": "00",
            "etxt_syear": s_year,
            "etxt_smonth": s_month,
            "etxt_sday": s_day,
            "etxt_eyear": e_year,
            "etxt_emonth": e_month,
            "etxt_eday": e_day,
            "spath": "",
            "sdate": sdate,
            "edate": edate,
        }

        resp = self.session.post(self.settings.absence_view_url, data=payload, verify=False, timeout=20)
        resp.raise_for_status()

        return resp.text

    def submit_leave(self, target_date: date, target_periods: set[str]) -> str:
        leave_type_id = self.settings.leave_type_id
        leave_type_name = self.settings.leave_type_name
        leave_reason = self.settings.leave_reason
        period_order = self.settings.leave_period_order

        if not leave_type_id or not leave_type_name or not leave_reason:
            raise RuntimeError(
                "自動請假需要設定 .env：TPCU_LEAVE_ID / TPCU_LEAVE_NAME / TPCU_LEAVE_REASON"
            )
        if not period_order:
            raise RuntimeError("自動請假需要設定 .env：TPCU_LEAVE_PERIODS")

        _, _, _, compact = roc_date_parts(target_date)
        lea_value = build_lea_value(compact, period_order, target_periods, leave_type_id)

        payload = {
            "rdo1": f"{leave_type_id}#{leave_type_name}",
            "std_reason": leave_reason,
            "ls_date1": compact,
            "leaveid": leave_type_id,
            "leavename": leave_type_name,
            "lea_value": lea_value,
            "ls_chk": "Y",
            "todo": "upload",
        }
        files = {"uploadfile": ("", b"", "application/octet-stream")}

        resp = self.session.post(
            self.settings.leave_apply_url,
            data=payload,
            files=files,
            verify=False,
            timeout=20,
        )
        resp.raise_for_status()
        return resp.text

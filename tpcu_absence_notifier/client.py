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

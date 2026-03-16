import os
from datetime import datetime, timedelta

import requests
import urllib3
from bs4 import BeautifulSoup
from dotenv import load_dotenv

urllib3.disable_warnings()

load_dotenv()

BASE = "https://siw.tpcu.edu.tw"
LOGIN_URL = BASE + "/tsint/perchk.jsp"
ABSENCE_VIEW_URL = BASE + "/tsint/ak_pro/ak002_01.jsp"

UID = os.getenv("TPCU_UID")
PWD = os.getenv("TPCU_PWD")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
SCHOOL_YEAR_SEMESTER = os.getenv("TPCU_YMS", "114,2")

if not UID or not PWD or not DISCORD_WEBHOOK:
    raise RuntimeError("請先設定 .env：TPCU_UID / TPCU_PWD / DISCORD_WEBHOOK")

session = requests.Session()

def login() -> None:
    payload = {
        "hid_type": "S",
        "uid": UID,
        "pwd": PWD,
        "err": "N",
        "fncid": "",
        "ls_chochk": "N",
    }

    resp = session.post(LOGIN_URL, data=payload, verify=False, timeout=15)
    resp.raise_for_status()

    if "無此帳號或密碼" in resp.text:
        raise RuntimeError("登入失敗：帳號或密碼錯誤")

    if "JSESSIONID" not in session.cookies.get_dict():
        raise RuntimeError("登入失敗：未取得 JSESSIONID")

    print("登入成功")

def roc_date_parts(dt: datetime) -> tuple[str, str, str, str]:
    roc_year = str(dt.year - 1911)
    month = dt.strftime("%m")
    day = dt.strftime("%d")
    compact = f"{roc_year}{month}{day}"
    return roc_year, month, day, compact

def get_absence_html(days: int = 30) -> str:
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days)

    s_year, s_month, s_day, sdate = roc_date_parts(start_dt)
    e_year, e_month, e_day, edate = roc_date_parts(end_dt)

    payload = {
        "yms": SCHOOL_YEAR_SEMESTER,
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

    resp = session.post(ABSENCE_VIEW_URL, data=payload, verify=False, timeout=20)
    resp.raise_for_status()

    if "學生個人缺曠請假明細表" not in resp.text:
        with open("absence_debug.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        raise RuntimeError("查詢失敗：回應不是缺曠表，已輸出 absence_debug.html")

    return resp.text

def parse_absence(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")

    target_table = None
    for table in soup.find_all("table"):
        text = table.get_text(" ", strip=True)
        if "項次" in text and "日期" in text and "朝會" in text:
            target_table = table
            break

    if target_table is None:
        return []

    rows = target_table.find_all("tr")
    if len(rows) < 2:
        return []

    header_cells = [td.get_text(strip=True) for td in rows[0].find_all("td")]
    if len(header_cells) < 3:
        return []

    records: list[dict[str, str]] = []

    for row in rows[1:]:
        cols = [td.get_text(strip=True).replace("\xa0", "") for td in row.find_all("td")]
        if len(cols) != len(header_cells):
            continue

        item_no = cols[0]
        date = cols[1]

        for i in range(2, len(cols)):
            val = cols[i]
            if val:
                records.append(
                    {
                        "item": item_no,
                        "date": date,
                        "period": header_cells[i],
                        "type": val,
                    }
                )

    return records

def build_discord_message(records: list[dict[str, str]], days: int = 30) -> str:
    title = f"最近 {days} 天缺曠 / 請假紀錄"
    if not records:
        return f"{title}\n\n沒有紀錄"

    lines = [title, ""]
    for r in records:
        lines.append(f"{r['date']} 第{r['period']}節 - {r['type']}")

    content = "\n".join(lines)

    if len(content) <= 1900:
        return content

    trimmed = [title, ""]
    total = len("\n".join(trimmed))
    for line in lines[2:]:
        if total + len(line) + 1 > 1800:
            trimmed.append("...")
            break
        trimmed.append(line)
        total += len(line) + 1

    return "\n".join(trimmed)

def send_discord(records: list[dict[str, str]], days: int = 30) -> None:
    content = build_discord_message(records, days=days)

    payload = {"content": content}
    resp = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"Discord webhook 失敗：{resp.status_code} {resp.text}")

    print("Discord 已通知")

def main() -> None:
    days = 30

    login()

    html = get_absence_html(days=days)

    with open("absence_debug.html", "w", encoding="utf-8") as f:
        f.write(html)

    records = parse_absence(html)

    print(f"找到 {len(records)} 筆節次紀錄")
    for r in records[:10]:
        print(f"{r['date']} 第{r['period']}節 - {r['type']}")

    send_discord(records, days=days)

if __name__ == "__main__":
    main()
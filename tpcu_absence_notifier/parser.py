import re

from bs4 import BeautifulSoup

from .models import AbsenceRecord


DATE_PATTERN = re.compile(r"(\d{2,3})/(\d{1,2})/(\d{1,2})")


def normalize_roc_date(value: str) -> str:
    match = DATE_PATTERN.search(value.strip())
    if not match:
        return value.strip()

    year_str, month_str, day_str = match.groups()
    return f"{int(year_str):03d}/{int(month_str):02d}/{int(day_str):02d}"


def parse_absence(html: str) -> list[AbsenceRecord]:
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

    records: list[AbsenceRecord] = []

    for row in rows[1:]:
        cols = [td.get_text(strip=True).replace("\xa0", "") for td in row.find_all("td")]
        if len(cols) != len(header_cells):
            continue

        item_no = cols[0]
        date = normalize_roc_date(cols[1])

        for i in range(2, len(cols)):
            absence_type = cols[i]
            if absence_type:
                records.append(
                    AbsenceRecord(
                        item=item_no,
                        date=date,
                        period=header_cells[i],
                        absence_type=absence_type,
                    )
                )

    return records

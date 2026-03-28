from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    uid: str
    pwd: str
    discord_webhook: str
    school_year_semester: str = "114,2"
    output_dir: str = "outputs"
    base_url: str = "https://siw.tpcu.edu.tw"
    leave_type_id: str | None = None
    leave_type_name: str | None = None
    leave_reason: str | None = None
    leave_auto_types: tuple[str, ...] = ("缺", "曠")
    leave_period_order: tuple[str, ...] = ()
    leave_url: str | None = None
    leave_history_path: str | None = None

    @property
    def login_url(self) -> str:
        return f"{self.base_url}/tsint/perchk.jsp"

    @property
    def absence_view_url(self) -> str:
        return f"{self.base_url}/tsint/ak_pro/ak002_01.jsp"

    @property
    def leave_apply_url(self) -> str:
        if self.leave_url:
            return self.leave_url
        return f"{self.base_url}/tsint/ck_pro/ck001_ins.jsp"

    @property
    def debug_output_path(self) -> str:
        return str(Path(self.output_dir) / "debug" / "absence_debug.html")

    @property
    def leave_history_file(self) -> str:
        if self.leave_history_path:
            return self.leave_history_path
        return str(Path(self.output_dir) / "debug" / "leave_history.json")

    @property
    def chart_output_path(self) -> str:
        return str(Path(self.output_dir) / "charts" / "absence_chart.png")

    @property
    def table_output_path(self) -> str:
        return str(Path(self.output_dir) / "charts" / "absence_period_table.png")


def load_settings(
    *,
    require_webhook: bool = True,
    uid_override: str | None = None,
    pwd_override: str | None = None,
) -> Settings:
    load_dotenv()

    uid = uid_override or os.getenv("TPCU_UID")
    pwd = pwd_override or os.getenv("TPCU_PWD")
    discord_webhook = os.getenv("DISCORD_WEBHOOK")
    school_year_semester = os.getenv("TPCU_YMS", "114,2")
    output_dir = os.getenv("TPCU_OUTPUT_DIR", "outputs")
    leave_type_id = os.getenv("TPCU_LEAVE_ID")
    leave_type_name = os.getenv("TPCU_LEAVE_NAME")
    leave_reason = os.getenv("TPCU_LEAVE_REASON")
    leave_auto_types = tuple(
        value.strip()
        for value in os.getenv("TPCU_LEAVE_AUTO_TYPES", "缺,曠").split(",")
        if value.strip()
    )
    leave_period_order = tuple(
        value.strip()
        for value in os.getenv("TPCU_LEAVE_PERIODS", "").split(",")
        if value.strip()
    )
    leave_url = os.getenv("TPCU_LEAVE_URL")
    leave_history_path = os.getenv("TPCU_LEAVE_HISTORY_PATH")

    if not uid or not pwd:
        raise RuntimeError("請先設定 .env：TPCU_UID / TPCU_PWD")
    if require_webhook and not discord_webhook:
        raise RuntimeError("請先設定 .env：DISCORD_WEBHOOK")

    return Settings(
        uid=uid,
        pwd=pwd,
        discord_webhook=discord_webhook,
        school_year_semester=school_year_semester,
        output_dir=output_dir,
        leave_type_id=leave_type_id,
        leave_type_name=leave_type_name,
        leave_reason=leave_reason,
        leave_auto_types=leave_auto_types,
        leave_period_order=leave_period_order,
        leave_url=leave_url,
        leave_history_path=leave_history_path,
    )

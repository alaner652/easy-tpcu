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

    @property
    def login_url(self) -> str:
        return f"{self.base_url}/tsint/perchk.jsp"

    @property
    def absence_view_url(self) -> str:
        return f"{self.base_url}/tsint/ak_pro/ak002_01.jsp"

    @property
    def debug_output_path(self) -> str:
        return str(Path(self.output_dir) / "debug" / "absence_debug.html")

    @property
    def chart_output_path(self) -> str:
        return str(Path(self.output_dir) / "charts" / "absence_chart.png")

    @property
    def table_output_path(self) -> str:
        return str(Path(self.output_dir) / "charts" / "absence_period_table.png")


def load_settings() -> Settings:
    load_dotenv()

    uid = os.getenv("TPCU_UID")
    pwd = os.getenv("TPCU_PWD")
    discord_webhook = os.getenv("DISCORD_WEBHOOK")
    school_year_semester = os.getenv("TPCU_YMS", "114,2")
    output_dir = os.getenv("TPCU_OUTPUT_DIR", "outputs")

    if not uid or not pwd or not discord_webhook:
        raise RuntimeError("請先設定 .env：TPCU_UID / TPCU_PWD / DISCORD_WEBHOOK")

    return Settings(
        uid=uid,
        pwd=pwd,
        discord_webhook=discord_webhook,
        school_year_semester=school_year_semester,
        output_dir=output_dir,
    )

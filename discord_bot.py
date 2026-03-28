import asyncio
from collections import Counter
from datetime import date, datetime, timedelta
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from tpcu_absence_notifier.auto_leave import run_auto_leave
from tpcu_absence_notifier.client import TPCUClient
from tpcu_absence_notifier.config import load_settings
from tpcu_absence_notifier.summary import build_discord_description, build_discord_fields
from tpcu_absence_notifier.workflow import ensure_output_layout, run_absence_query


DEFAULT_LOOKBACK_DAYS = 30


def parse_date_arg(raw: str) -> date:
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"日期格式錯誤：{raw}，請使用 YYYY-MM-DD") from exc


def resolve_query_window(
    *,
    single_date: str | None,
    start_date: str | None,
    end_date: str | None,
    days: int,
) -> tuple[date, date]:
    if single_date and (start_date or end_date):
        raise ValueError("--date 不能和 --start-date / --end-date 同時使用")

    if single_date:
        parsed = parse_date_arg(single_date)
        return parsed, parsed

    if start_date or end_date:
        start = parse_date_arg(start_date or end_date)
        end = parse_date_arg(end_date or start_date)
    else:
        end = datetime.now().date()
        start = end - timedelta(days=days - 1)

    if start > end:
        raise ValueError("起始日期不能晚於結束日期")

    return start, end


def format_auto_leave_summary(results, logs: list[str], dry_run: bool) -> str:
    if dry_run:
        if not logs:
            return "乾跑：沒有需要送出的紀錄。"
        lines = logs[:8]
        more = len(logs) - len(lines)
        if more > 0:
            lines.append(f"...以及 {more} 筆")
        return "乾跑結果：\n" + "\n".join(lines)

    if not results:
        return "未送出任何請假。"

    counts = Counter(result.status for result in results)
    return (
        "已送出 "
        f"{len(results)} 筆（success {counts.get('success', 0)} / "
        f"failure {counts.get('failure', 0)} / "
        f"unknown {counts.get('unknown', 0)}）"
    )


def run_check_sync(
    *,
    start_date: date,
    end_date: date,
    auto_leave: bool,
    dry_run: bool,
    force: bool,
    uid: str,
    pwd: str,
) -> tuple[object, list, list[str]]:
    settings = load_settings(require_webhook=False, uid_override=uid, pwd_override=pwd)
    ensure_output_layout(settings)
    client = TPCUClient(settings)
    client.login()

    result = run_absence_query(
        client=client,
        settings=settings,
        start_date=start_date,
        end_date=end_date,
    )

    logs: list[str] = []
    auto_leave_results: list = []
    if auto_leave:
        auto_leave_results = run_auto_leave(
            client=client,
            records=result.records,
            settings=settings,
            dry_run=dry_run,
            force=force,
            logger=logs.append,
        )

    return result, auto_leave_results, logs


def build_embeds_and_files(
    *,
    title: str,
    description: str,
    fields: list[dict[str, object]],
    chart_path: str,
    table_path: str,
    auto_leave_summary: str | None = None,
) -> tuple[list[discord.Embed], list[discord.File]]:
    chart_file = discord.File(chart_path, filename=Path(chart_path).name)
    table_file = discord.File(table_path, filename=Path(table_path).name)

    embed = discord.Embed(title=title, description=description, color=0x2563EB)
    for field in fields:
        embed.add_field(
            name=str(field.get("name", "")),
            value=str(field.get("value", "")),
            inline=bool(field.get("inline", False)),
        )
    if auto_leave_summary:
        embed.add_field(name="自動請假", value=auto_leave_summary, inline=False)
    embed.set_image(url=f"attachment://{Path(chart_path).name}")

    table_embed = discord.Embed(color=0x0F766E)
    table_embed.set_image(url=f"attachment://{Path(table_path).name}")

    return [embed, table_embed], [chart_file, table_file]


class TPCUBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        guild_id = os.getenv("DISCORD_GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()


bot = TPCUBot()


@bot.tree.command(name="check", description="查詢缺曠 / 請假紀錄")
@app_commands.describe(
    uid="你的學號",
    pwd="你的密碼",
    date="查詢單日（YYYY-MM-DD）",
    start_date="起始日（YYYY-MM-DD）",
    end_date="結束日（YYYY-MM-DD）",
    days="未指定日期時，往前查詢天數（預設 30）",
)
async def check(
    interaction: discord.Interaction,
    uid: str,
    pwd: str,
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    days: int = DEFAULT_LOOKBACK_DAYS,
) -> None:
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        start, end = resolve_query_window(
            single_date=date,
            start_date=start_date,
            end_date=end_date,
            days=days,
        )
    except ValueError as exc:
        await interaction.followup.send(f"參數錯誤：{exc}", ephemeral=True)
        return

    try:
        result, _auto_leave_results, _logs = await asyncio.to_thread(
            run_check_sync,
            start_date=start,
            end_date=end,
            auto_leave=False,
            dry_run=False,
            force=False,
            uid=uid,
            pwd=pwd,
        )
    except Exception as exc:
        await interaction.followup.send(f"查詢失敗：{exc}", ephemeral=True)
        return

    embeds, files = build_embeds_and_files(
        title="TPCU 缺曠 / 請假查詢",
        description=build_discord_description(result.records),
        fields=build_discord_fields(result.records, start, end),
        chart_path=result.chart_path,
        table_path=result.table_path,
    )
    await interaction.followup.send(embeds=embeds, files=files, ephemeral=True)


@bot.tree.command(name="auto_leave", description="查詢缺曠並自動送出請假")
@app_commands.describe(
    uid="你的學號",
    pwd="你的密碼",
    date="查詢單日（YYYY-MM-DD）",
    start_date="起始日（YYYY-MM-DD）",
    end_date="結束日（YYYY-MM-DD）",
    days="未指定日期時，往前查詢天數（預設 30）",
    dry_run="只列出將送出的請假，不實際送出",
    force="忽略去重紀錄，強制送出",
)
async def auto_leave(
    interaction: discord.Interaction,
    uid: str,
    pwd: str,
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    days: int = DEFAULT_LOOKBACK_DAYS,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        start, end = resolve_query_window(
            single_date=date,
            start_date=start_date,
            end_date=end_date,
            days=days,
        )
    except ValueError as exc:
        await interaction.followup.send(f"參數錯誤：{exc}", ephemeral=True)
        return

    try:
        result, auto_leave_results, logs = await asyncio.to_thread(
            run_check_sync,
            start_date=start,
            end_date=end,
            auto_leave=True,
            dry_run=dry_run,
            force=force,
            uid=uid,
            pwd=pwd,
        )
    except Exception as exc:
        await interaction.followup.send(f"查詢失敗：{exc}", ephemeral=True)
        return

    auto_leave_summary = format_auto_leave_summary(auto_leave_results, logs, dry_run)
    embeds, files = build_embeds_and_files(
        title="TPCU 缺曠 / 請假查詢",
        description=build_discord_description(result.records),
        fields=build_discord_fields(result.records, start, end),
        chart_path=result.chart_path,
        table_path=result.table_path,
        auto_leave_summary=auto_leave_summary,
    )
    await interaction.followup.send(embeds=embeds, files=files, ephemeral=True)


def main() -> None:
    load_dotenv()
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("請先設定 .env：DISCORD_BOT_TOKEN")
    bot.run(token)


if __name__ == "__main__":
    main()

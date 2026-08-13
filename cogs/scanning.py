from __future__ import annotations

import logging
from datetime import time, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from core.analyze_service import analyze
from core.config import Config
from core.scan_service import run_scan
from core.storage import cycle_active

log = logging.getLogger("clverboard.scanning")


class ScanningCog(commands.Cog):
    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config
        self.daily_check.change_interval(time=time(hour=config.scan_hour_utc, tzinfo=timezone.utc))
        self.daily_check.start()

    def cog_unload(self):
        self.daily_check.cancel()

    def _is_staff(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False
        return any(role.id == self.config.staff_role_id for role in interaction.user.roles)

    @app_commands.command(name="clverboard-scan", description="Manually start a ClverBoard scan")
    async def clverboard_scan(self, interaction: discord.Interaction):
        if not self._is_staff(interaction):
            await interaction.response.send_message("You don't have permission to run this.", ephemeral=True)
            return

        if cycle_active():
            await interaction.response.send_message(
                "A ClverBoard cycle is already pending review. Complete it before starting a new scan.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        candidates, period_start, period_end = await run_scan(self.bot, self.config)
        qualifying = analyze(candidates, self.config.reaction_threshold)

        if qualifying:
            verification_cog = self.bot.get_cog("VerificationCog")
            await verification_cog.start_review(qualifying, period_start, period_end)

        await interaction.followup.send(
            f"Scan complete. Collected {len(candidates)} candidate post(s), "
            f"{len(qualifying)} met the reaction threshold and were sent for staff review "
            f"(period {period_start.date()} to {period_end.date()}).",
            ephemeral=True,
        )

    @tasks.loop(hours=24)
    async def daily_check(self):
        today = discord.utils.utcnow().day
        if not any(lo <= today <= hi for lo, hi in self.config.cycle_trigger_days):
            return
        if cycle_active():
            log.info("Skipping scheduled scan: previous cycle still pending review.")
            return

        guild = self.bot.get_guild(self.config.guild_id)
        if guild is None:
            log.warning("Configured guild %s not found; skipping scheduled scan.", self.config.guild_id)
            return

        candidates, period_start, period_end = await run_scan(self.bot, self.config)
        qualifying = analyze(candidates, self.config.reaction_threshold)

        if qualifying:
            verification_cog = self.bot.get_cog("VerificationCog")
            await verification_cog.start_review(qualifying, period_start, period_end)

        log.info(
            "Scheduled scan complete: %d candidate(s) collected, %d sent for review.",
            len(candidates),
            len(qualifying),
        )

    @daily_check.before_loop
    async def before_daily_check(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(ScanningCog(bot, bot.clverboard_config))

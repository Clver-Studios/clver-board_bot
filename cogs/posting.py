from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from discord.ext import commands

from core import storage
from core.config import Config
from core.discord_utils import get_channel
from core.embeds import build_board_embed
from core.models import Candidate

log = logging.getLogger("clverboard.posting")


class PostingCog(commands.Cog):
    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config
        self._task: asyncio.Task | None = None

    async def cog_load(self):
        # If the bot restarted mid-delay, resume the pending post instead of losing it.
        cycle = storage.load_cycle()
        if cycle and cycle.get("stage") == "posting":
            log.info("Resuming pending ClverBoard posting after restart.")
            self._task = asyncio.create_task(self._run_after_delay(cycle))

    def cog_unload(self):
        if self._task is not None:
            self._task.cancel()

    async def schedule_posting(self, approved_candidates: list[Candidate]) -> None:
        """Called by VerificationCog once every candidate in a cycle has a decision."""
        post_after = datetime.now(timezone.utc) + timedelta(seconds=self.config.posting_delay_seconds)
        cycle = {
            "stage": "posting",
            "post_after": post_after.isoformat(),
            "candidates": [c.to_dict() for c in approved_candidates],
        }
        storage.save_cycle(cycle)
        log.info(
            "Verification complete: %d approved post(s) will publish at %s.",
            len(approved_candidates),
            post_after.isoformat(),
        )
        self._task = asyncio.create_task(self._run_after_delay(cycle))

    async def _run_after_delay(self, cycle: dict) -> None:
        post_after = datetime.fromisoformat(cycle["post_after"])
        delay = (post_after - datetime.now(timezone.utc)).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)
        await self._publish(cycle)

    async def _publish(self, cycle: dict) -> None:
        candidates = [Candidate.from_dict(c) for c in cycle["candidates"]]
        posted_ids = storage.load_posted_ids()
        to_post = [c for c in candidates if c.message_id not in posted_ids]
        skipped = len(candidates) - len(to_post)
        if skipped:
            log.info("Skipped %d duplicate candidate(s) already on the ClverBoard.", skipped)

        if to_post:
            channel = await get_channel(self.bot, self.config.posting_channel_id)
            for candidate in to_post:
                await channel.send(embed=build_board_embed(candidate))

        storage.add_posted_ids([c.message_id for c in candidates])
        storage.clear_cycle()
        log.info("ClverBoard posting complete: %d post(s) published.", len(to_post))


async def setup(bot: commands.Bot):
    await bot.add_cog(PostingCog(bot, bot.clverboard_config))

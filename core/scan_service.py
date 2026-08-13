from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import discord

from .config import Config
from .models import Candidate

log = logging.getLogger("clverboard.scan")


def _extract_image(message: discord.Message) -> str | None:
    for att in message.attachments:
        if att.content_type and att.content_type.startswith("image/"):
            return att.url
    for embed in message.embeds:
        if embed.image and embed.image.url:
            return embed.image.url
    return None


def _build_candidate(message: discord.Message, *, thread: discord.Thread | None = None) -> Candidate | None:
    reaction_count = sum(r.count for r in message.reactions)
    if reaction_count == 0:
        return None

    channel = thread or message.channel
    return Candidate(
        message_id=message.id,
        author_id=message.author.id,
        author_name=str(message.author),
        channel_id=channel.id,
        channel_name=getattr(channel, "name", str(channel.id)),
        is_thread=thread is not None,
        content=message.content or "",
        reaction_count=reaction_count,
        timestamp=message.created_at.isoformat(),
        jump_url=message.jump_url,
        image_url=_extract_image(message),
    )


async def _scan_channel(
    channel: discord.abc.GuildChannel, period_start: datetime, period_end: datetime
) -> list[Candidate]:
    candidates: list[Candidate] = []

    if isinstance(channel, discord.ForumChannel):
        for thread in channel.threads:
            if not (period_start <= thread.created_at <= period_end):
                continue
            msg = thread.starter_message
            if msg is None:
                try:
                    msg = await thread.fetch_message(thread.id)
                except (discord.NotFound, discord.Forbidden):
                    continue
            candidate = _build_candidate(msg, thread=thread)
            if candidate:
                candidates.append(candidate)
        return candidates

    if not isinstance(channel, discord.TextChannel):
        return candidates

    async for message in channel.history(after=period_start, before=period_end, limit=None, oldest_first=True):
        if message.author.bot:
            continue
        candidate = _build_candidate(message)
        if candidate:
            candidates.append(candidate)
    return candidates


async def run_scan(client: discord.Client, config: Config) -> tuple[list[Candidate], datetime, datetime]:
    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=config.period_days)

    all_candidates: list[Candidate] = []
    for channel_id in config.scan_channel_ids:
        channel = client.get_channel(channel_id)
        if channel is None:
            log.warning("Scan channel %s not found or not cached", channel_id)
            continue
        try:
            all_candidates.extend(await _scan_channel(channel, period_start, period_end))
        except discord.Forbidden:
            log.warning("Missing permissions to read channel %s", channel_id)
        except discord.HTTPException as exc:
            log.warning("Failed to scan channel %s: %s", channel_id, exc)

    return all_candidates, period_start, period_end

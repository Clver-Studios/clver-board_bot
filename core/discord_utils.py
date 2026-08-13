from __future__ import annotations

import discord
from discord.ext import commands


async def get_channel(bot: commands.Bot, channel_id: int) -> discord.abc.Messageable:
    """Return a channel from cache, falling back to an API fetch (minimizes requests)."""
    channel = bot.get_channel(channel_id)
    if channel is None:
        channel = await bot.fetch_channel(channel_id)
    return channel

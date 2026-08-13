from __future__ import annotations

import discord

from .models import Candidate

APPROVAL_COLOR = discord.Color.blurple()
APPROVED_COLOR = discord.Color.green()
REJECTED_COLOR = discord.Color.red()
BOARD_COLOR = discord.Color.gold()


def _base_embed(candidate: Candidate, *, color: discord.Color) -> discord.Embed:
    embed = discord.Embed(
        description=candidate.content[:1024] or "*(no text content)*",
        color=color,
        timestamp=discord.utils.parse_time(candidate.timestamp),
    )
    embed.set_author(name=candidate.author_name)
    embed.add_field(name="Reactions", value=str(candidate.reaction_count), inline=True)
    embed.add_field(name="Channel", value=f"#{candidate.channel_name}", inline=True)
    embed.add_field(name="Jump to post", value=f"[Open message]({candidate.jump_url})", inline=True)
    if candidate.image_url:
        embed.set_image(url=candidate.image_url)
    return embed


def build_approval_embed(candidate: Candidate) -> discord.Embed:
    """Embed shown in the approval channel while a candidate awaits a staff decision."""
    embed = _base_embed(candidate, color=APPROVAL_COLOR)
    embed.title = "ClverBoard Candidate — Awaiting Review"
    return embed


def build_decided_embed(candidate: Candidate, decided_by: str) -> discord.Embed:
    """Embed shown in the approval channel after a staff decision, replacing the buttons."""
    color = APPROVED_COLOR if candidate.status == "approved" else REJECTED_COLOR
    embed = _base_embed(candidate, color=color)
    label = "Approved" if candidate.status == "approved" else "Rejected"
    embed.title = f"ClverBoard Candidate — {label}"
    embed.set_footer(text=f"{label} by {decided_by}")
    return embed


def build_board_embed(candidate: Candidate) -> discord.Embed:
    """Embed published to the public ClverBoard channel."""
    embed = _base_embed(candidate, color=BOARD_COLOR)
    embed.title = "🏆 ClverBoard"
    return embed

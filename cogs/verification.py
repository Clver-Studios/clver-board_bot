from __future__ import annotations

import logging

import discord
from discord.ext import commands

from core import storage
from core.config import Config
from core.discord_utils import get_channel
from core.embeds import build_approval_embed, build_decided_embed
from core.models import Candidate

log = logging.getLogger("clverboard.verification")


class ApprovalView(discord.ui.View):
    """Persistent view attached to every candidate posted in the approval channel.

    Buttons use static custom_ids; the actual candidate is resolved from the
    interaction's message id against the on-disk cycle state, so a single
    registered view instance (added once in setup_hook) handles every message.
    """

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, custom_id="clverboard:approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("VerificationCog")
        if cog is not None:
            await cog.handle_decision(interaction, approved=True)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, custom_id="clverboard:reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("VerificationCog")
        if cog is not None:
            await cog.handle_decision(interaction, approved=False)


class VerificationCog(commands.Cog):
    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config

    def _is_staff(self, member: discord.abc.User) -> bool:
        if not isinstance(member, discord.Member):
            return False
        return any(role.id == self.config.staff_role_id for role in member.roles)

    async def start_review(self, candidates: list[Candidate], period_start, period_end) -> None:
        """Post ranked candidates to the approval channel and persist the review cycle."""
        channel = await get_channel(self.bot, self.config.approval_channel_id)

        for candidate in candidates:
            message = await channel.send(embed=build_approval_embed(candidate), view=ApprovalView())
            candidate.approval_message_id = message.id
            candidate.status = "pending"

        storage.start_review(candidates, period_start, period_end)
        log.info("Sent %d candidate(s) for staff verification.", len(candidates))

    async def handle_decision(self, interaction: discord.Interaction, *, approved: bool) -> None:
        if not self._is_staff(interaction.user):
            await interaction.response.send_message("You don't have permission to do this.", ephemeral=True)
            return

        cycle = storage.load_cycle()
        if cycle is None or cycle.get("stage") != "review":
            await interaction.response.send_message(
                "This ClverBoard cycle is no longer active.", ephemeral=True
            )
            return

        candidates = [Candidate.from_dict(c) for c in cycle["candidates"]]
        target = next((c for c in candidates if c.approval_message_id == interaction.message.id), None)
        if target is None:
            await interaction.response.send_message(
                "Couldn't find this candidate in the active cycle.", ephemeral=True
            )
            return

        if target.status != "pending":
            await interaction.response.send_message(
                f"Already {target.status} by another staff member.", ephemeral=True
            )
            return

        target.status = "approved" if approved else "rejected"
        cycle["candidates"] = [c.to_dict() for c in candidates]
        storage.save_cycle(cycle)

        await interaction.response.edit_message(
            embed=build_decided_embed(target, decided_by=str(interaction.user)), view=None
        )

        if any(c.status == "pending" for c in candidates):
            return

        # Verification is complete for every candidate in this cycle.
        approved_candidates = [c for c in candidates if c.status == "approved"]
        posting_cog = self.bot.get_cog("PostingCog")
        if not approved_candidates:
            log.info("Verification complete: no candidates approved, nothing to post.")
            storage.clear_cycle()
            return

        if posting_cog is None:
            log.warning("PostingCog not loaded; cannot schedule ClverBoard posting.")
            return

        await posting_cog.schedule_posting(approved_candidates)


async def setup(bot: commands.Bot):
    await bot.add_cog(VerificationCog(bot, bot.clverboard_config))

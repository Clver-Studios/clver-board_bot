from __future__ import annotations

import logging
import sys

import discord
from discord.ext import commands

from core.config import Config, ConfigError

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("clverboard")


class StartupError(RuntimeError):
    """A startup stage failed for a reason the operator needs to act on."""


class ClverBoardBot(commands.Bot):
    def __init__(self, config: Config):
        intents = discord.Intents.default()
        # Required: scan_service reads message.content when building candidates.
        # Enable under Developer Portal -> your app -> Bot -> Privileged Gateway Intents.
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.clverboard_config = config

    async def setup_hook(self):
        # Persistent view for Approve/Reject buttons: uses static custom_ids, so one
        # registration here covers every approval message across restarts.
        from cogs.verification import ApprovalView

        self.add_view(ApprovalView())

        await self._check_privileged_intents()

        await self.load_extension("cogs.scanning")
        await self.load_extension("cogs.verification")
        await self.load_extension("cogs.posting")

        guild = await self._resolve_guild()
        await self._sync_commands(guild)

    async def _check_privileged_intents(self) -> None:
        """Stage: Confirm Bot Identity.

        setup_hook runs before the gateway IDENTIFY, so a privileged intent that is
        requested but not enabled would otherwise surface only after several silent
        'session has been invalidated' reconnects (~30-60s of noise). The application's
        own flags tell us up front, so fail here with the actual reason.
        """
        app = await self.application_info()
        flags = app.flags
        if not (flags.gateway_message_content or flags.gateway_message_content_limited):
            raise StartupError(
                f"The Message Content privileged intent is not enabled for application "
                f"'{app.name}' (id {app.id}), but this bot requires it to read post content.\n"
                f"  Enable it at: https://discord.com/developers/applications/{app.id}/bot\n"
                f"  -> Privileged Gateway Intents -> MESSAGE CONTENT INTENT -> Save Changes"
            )
        log.info("Privileged intents OK (message content enabled).")

    async def _resolve_guild(self) -> discord.Guild:
        """Stage: Resolve Configured Guild.

        Runs before the sync so a bad/foreign guild id is reported as exactly that,
        instead of surfacing as a bare 403 from the command-sync call.
        """
        guild_id = self.clverboard_config.guild_id
        log.info("Resolving configured guild %s ...", guild_id)
        try:
            guild = await self.fetch_guild(guild_id)
        except (discord.NotFound, discord.Forbidden):
            # Discord answers 404 Unknown Guild for a guild the bot is not a member of,
            # so "wrong id" and "not invited" are indistinguishable here - report both.
            raise StartupError(
                f"Bot '{self.user}' cannot see guild_id={guild_id}. Either:\n"
                f"  1. config.json -> guild_id is wrong "
                f"(right-click your server -> Copy Server ID, with Developer Mode on), or\n"
                f"  2. this bot was never invited to that server - re-invite it with "
                f"both the 'bot' and 'applications.commands' scopes."
            ) from None
        log.info("Resolved guild: %s (%s)", guild.name, guild.id)
        return guild

    async def _sync_commands(self, guild: discord.Guild) -> None:
        """Stage: Synchronize Commands."""
        try:
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
        except discord.Forbidden:
            raise StartupError(
                f"Command sync to '{guild.name}' ({guild.id}) was refused (403 Missing Access). "
                f"The bot is in the server but lacks the 'applications.commands' scope. "
                f"Re-invite it with both the 'bot' and 'applications.commands' scopes."
            ) from None
        log.info("Synced %d command(s) to %s (%s).", len(synced), guild.name, guild.id)

    async def on_ready(self):
        log.info("Logged in as %s - ClverBoard systems ready.", self.user)


def main():
    try:
        config = Config.load()
    except ConfigError as exc:
        log.error("Startup failed at stage 'Load Configuration': %s", exc)
        sys.exit(1)

    bot = ClverBoardBot(config)
    try:
        # log_handler=None: basicConfig above already handles the root logger. Letting
        # run() install its own handler too would print every discord.* line twice.
        bot.run(config.token, log_handler=None)
    except discord.LoginFailure:
        log.error(
            "Startup failed at stage 'Connect to Discord': the bot token was rejected. "
            "Check DISCORD_TOKEN in .env - regenerate it in the Developer Portal if needed."
        )
        sys.exit(1)
    except discord.PrivilegedIntentsRequired:
        log.error(
            "Startup failed at stage 'Connect to Discord': the Message Content privileged "
            "intent is not enabled for this application. Enable it under Developer Portal -> "
            "your app -> Bot -> Privileged Gateway Intents."
        )
        sys.exit(1)
    except StartupError as exc:
        log.error("Startup failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()

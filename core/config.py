from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

# Every id in config.json is a Discord snowflake. The example file ships them as 0,
# so 0 means "copied the template but never filled this in" - catching that here turns
# an opaque downstream 403 into a named configuration error.
REQUIRED_IDS = ("guild_id", "approval_channel_id", "posting_channel_id", "staff_role_id")


class ConfigError(RuntimeError):
    """Raised when configuration is missing or still holds template placeholders."""


@dataclass(frozen=True)
class Config:
    token: str
    guild_id: int
    scan_channel_ids: list[int]
    approval_channel_id: int
    posting_channel_id: int
    staff_role_id: int
    period_days: int
    cycle_trigger_days: list[list[int]]
    scan_hour_utc: int
    reaction_threshold: int
    posting_delay_seconds: int

    @classmethod
    def load(cls) -> "Config":
        token = os.environ.get("DISCORD_TOKEN")
        if not token:
            raise ConfigError("DISCORD_TOKEN is not set (check .env)")
        if not CONFIG_PATH.exists():
            raise ConfigError(f"Missing config file: {CONFIG_PATH}")

        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls._validate(data)
        return cls(
            token=token,
            guild_id=int(data["guild_id"]),
            scan_channel_ids=[int(c) for c in data["scan_channel_ids"]],
            approval_channel_id=int(data["approval_channel_id"]),
            posting_channel_id=int(data["posting_channel_id"]),
            staff_role_id=int(data["staff_role_id"]),
            period_days=int(data.get("period_days", 15)),
            cycle_trigger_days=data.get("cycle_trigger_days", [[5, 9], [21, 25]]),
            scan_hour_utc=int(data.get("scan_hour_utc", 12)),
            reaction_threshold=int(data.get("reaction_threshold", 3)),
            posting_delay_seconds=int(data.get("posting_delay_seconds", 240)),
        )

    @staticmethod
    def _validate(data: dict) -> None:
        missing = [key for key in REQUIRED_IDS if key not in data]
        if missing:
            raise ConfigError(
                f"config.json is missing required key(s): {', '.join(missing)}. "
                f"Compare against config.example.json."
            )

        unset = [key for key in REQUIRED_IDS if int(data[key]) <= 0]
        if unset:
            raise ConfigError(
                f"config.json still has placeholder value(s) for: {', '.join(unset)}. "
                f"Replace each 0 with the real Discord id "
                f"(Discord -> User Settings -> Advanced -> Developer Mode, then right-click -> Copy ID)."
            )

        if not data.get("scan_channel_ids"):
            raise ConfigError(
                "config.json has an empty scan_channel_ids - the bot would have no channels to scan."
            )
        bad_scan = [c for c in data["scan_channel_ids"] if int(c) <= 0]
        if bad_scan:
            raise ConfigError(f"config.json has placeholder scan_channel_ids: {bad_scan}.")

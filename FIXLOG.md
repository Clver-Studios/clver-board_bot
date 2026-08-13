# ClverBoard Bot — Fix Log

### `2026-08-13 — Startup Logging: Duplicate Lines & Buried Fatal Cause`

| Field | Details |
| --- | --- |
| **Symptom** | Every `discord.*` log line printed twice, and a fatal misconfiguration took ~60s of repeating `session has been invalidated` lines before the real reason appeared. |
| **Error** | No exception — log noise obscuring `PrivilegedIntentsRequired`. |
| **Failure Point** | `logging.basicConfig()` in `bot.py`; `bot.run()` default `log_handler`. |
| **Root Cause** | Two causes. (1) `basicConfig()` attaches a handler to the root logger, and `bot.run()` separately installs discord.py's own handler on the `discord` logger — both fired, so each line was emitted twice in two different formats. (2) `setup_hook()` runs *before* the gateway IDENTIFY, so a requested-but-not-enabled privileged intent only surfaced after discord.py exhausted its silent reconnect attempts. |
| **Fix** | (1) `bot.run(..., log_handler=None)` plus an explicit `basicConfig` format, giving one consistently formatted line per event. (2) Added `_check_privileged_intents()` at the *Confirm Bot Identity* stage: it reads the application's own gateway flags via `application_info()` and fails immediately with the app name, ID, and a direct link to the setting to change. |
| **Verification** | Live run: log output is single-line and consistently formatted; the intent misconfiguration now fails in ~2s (was ~60s) naming the exact cause. Separately confirmed every stage *after* the intent gate is clean — all three cogs load, guild resolves, `clverboard-scan` syncs, gateway connects, READY reached, exit 0. |
| **Status** | **Resolved** |
| **Durable Lesson** | Startup checks belong before the operation they gate, not after. A precondition validated only by the failure it causes turns a one-line config error into a minute of unrelated retry noise. Also: configure logging in exactly one place — a library that helpfully sets up logging will happily duplicate yours. |

---

### `2026-08-13 — Guild Command Sync: Missing Access`

| Field | Details |
| --- | --- |
| **Symptom** | Bot authenticated successfully but failed during guild command synchronization. |
| **Error** | `403 Forbidden — error code 50001: Missing Access` |
| **Failure Point** | `self.tree.sync(guild=guild)` in `bot.py` `setup_hook()` |
| **Root Cause** | `config.json` was copied from `config.example.json` and every ID was filled in **except** `guild_id`, which was left at the placeholder `0`. `setup_hook()` built `discord.Object(id=0)` and synced against it; guild `0` does not exist, so Discord answered `403 Missing Access`. `Config.load()` validated only the token, so the placeholder passed straight through to the API call. |
| **Fix** | 1. Set `config.json` → `guild_id` to the real server ID (confirmed by a read-only diagnostic: the bot is a member of exactly one guild, and every other configured channel/role ID resolves inside it). 2. Added `Config._validate()` so placeholder/missing IDs fail at the *Load Configuration* stage with a message naming the offending key. 3. Split startup into named stages — the guild is now resolved via `fetch_guild()` *before* the sync, so an access failure reports whether the guild is unreachable or the `applications.commands` scope is missing. |
| **Verification** | Live run against Discord: configuration loaded and validated, login succeeded, guild resolved (`Resolved guild: <name> (<id>)`), and `Synced 1 command(s)` — the original 403 no longer occurs. Validation tested against four bad configs (`guild_id=0`, `approval_channel_id=0`, empty `scan_channel_ids`, missing key), each rejected with the correct message. Unreachable-guild diagnostics tested with two bad guild IDs. |
| **Status** | **Resolved** — the reported 403 is fixed. Full runtime pipeline still **blocked** on enabling the Message Content privileged intent (external Developer Portal action; see Remaining Work). |
| **Durable Lesson** | Placeholder config values must fail at load time, not at first use. A `0` ID travelling into an API call surfaces as a permissions error, which sends diagnosis toward Discord roles/scopes instead of toward the config file that is actually wrong. Validate configuration at the boundary and name the failing stage. |

#### Discovered during verification

Two issues surfaced that were invisible behind the original 403:

1. **Message Content intent not enabled.** `setup_hook()` runs *before* the gateway
   IDENTIFY, so the sync failure aborted startup before the intent check was ever
   reached. With the sync fixed, the connection now proceeds far enough to fail with
   `PrivilegedIntentsRequired`. This must be enabled in the Developer Portal — it cannot
   be fixed in code, and the bot genuinely needs it (`core/scan_service.py` reads
   `message.content`).
2. **`members` intent was requested but unused.** Staff checks read roles from the
   interaction payload, which Discord always supplies. It was removed, reducing the
   privileged intents that must be enabled from two to one.

Also fixed: the new diagnostic messages originally contained `→`/`—` characters, which
raised `UnicodeEncodeError` when logged to a cp1252 Windows console — the error handler
would itself have crashed. All runtime strings are now ASCII.

---

## Remaining Work

* ~~Enable the Message Content privileged intent.~~ **Done 2026-08-13** — enabled in the
  Developer Portal for the ClverBoard Bot application. Presence and Server Members
  intents were deliberately left **off**; the bot does not request them.

Nothing outstanding. The bot starts, reaches ready, and runs the pipeline end to end
through staff verification.

## Future Considerations

Unrelated to this failure; recorded, not acted on.

* The manual command is named `/clverboard-scan`, while the project spec refers to it as
  `/clverboard`. Renaming is a one-line change but would alter an existing command
  surface, so it was left alone.
* `cogs/scanning.py` calls `verification_cog.start_review(...)` without checking that
  `get_cog("VerificationCog")` returned a value; `cogs/verification.py` does guard the
  equivalent `PostingCog` lookup. Inconsistent, but not reachable in the current startup
  path since all three cogs load together.
* `core/discord_utils.get_channel()` lets `fetch_channel` raise on a misconfigured
  channel ID. A stage-named error there would match the new startup diagnostics.

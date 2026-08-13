# ClverBoard Bot — Setup

Step-by-step setup for a clean machine, plus how to diagnose the startup errors that
actually occur in practice.

> No real tokens or server IDs appear in this file. Both `.env` and `config.json` are
> gitignored — keep them that way.

---

## 1. Requirements

* **Python 3.11+** (verified on 3.14.4)
* Dependencies, from `requirements.txt`:
  * `discord.py>=2.4.0` (verified on 2.7.1)
  * `python-dotenv>=1.0.0`

Voice dependencies (`PyNaCl`, `davey`) are **not** required. The two warnings they
produce on startup are harmless — the bot uses no voice features:

```text
WARNING:discord.client:PyNaCl is not installed, voice will NOT be supported
WARNING:discord.client:davey is not installed, voice will NOT be supported
```

---

## 2. Installation

```powershell
cd "C:\path\to\ClverBoardBot"
pip install -r requirements.txt
```

---

## 3. Configuration

### 3a. Bot token — `.env`

```powershell
copy .env.example .env
```

Then edit `.env`:

```env
DISCORD_TOKEN=your-bot-token-here
```

Get the token from the [Developer Portal](https://discord.com/developers/applications) →
your application → **Bot** → **Reset Token**. Never commit or paste this value anywhere.

### 3b. Operational settings — `config.json`

```powershell
copy config.example.json config.json
```

Every `0` in the template is a placeholder you **must** replace with a real Discord ID.
To copy IDs, first enable **Discord → User Settings → Advanced → Developer Mode**, then
right-click a server/channel/role → **Copy ID**.

| Key | Type | How to get it |
| --- | --- | --- |
| `guild_id` | int | Right-click your server name → Copy Server ID |
| `scan_channel_ids` | list[int] | Right-click each channel to scan → Copy Channel ID |
| `approval_channel_id` | int | Staff-only channel where candidates are reviewed |
| `posting_channel_id` | int | Public channel where approved posts are published |
| `staff_role_id` | int | Server Settings → Roles → right-click role → Copy Role ID |
| `period_days` | int | How many days back a scan looks (default `15`) |
| `cycle_trigger_days` | list[[int,int]] | Day-of-month windows the scheduled scan may run in |
| `scan_hour_utc` | int | UTC hour of the daily scheduled check (default `12`) |
| `reaction_threshold` | int | Minimum total reactions to qualify (default `3`) |
| `posting_delay_seconds` | int | Delay before publishing (default `240`) |

Startup validates these before connecting to Discord. A leftover `0` fails immediately
with a message naming the exact key, rather than failing later as an opaque HTTP error.

---

## 4. Discord application setup

In the [Developer Portal](https://discord.com/developers/applications) → your application:

### Bot → Privileged Gateway Intents

* **MESSAGE CONTENT INTENT** — **required**. `core/scan_service.py` reads
  `message.content` to build candidate embeds. Without it the bot cannot finish
  connecting and exits with `PrivilegedIntentsRequired`.
* **SERVER MEMBERS INTENT** — *not* required. Staff permission checks read roles from
  the interaction payload, which Discord always includes.

### OAuth2 → URL Generator

Select **both** scopes — `applications.commands` is what permits slash-command sync:

* `bot`
* `applications.commands`

Bot permissions needed:

* View Channels
* Read Message History
* Send Messages
* Embed Links

Open the generated URL and invite the bot to your server.

---

## 5. Server configuration

Confirm in Discord that:

1. The bot is a **member** of the server whose ID is in `config.json` → `guild_id`.
2. The bot can **view** and **read message history** in every `scan_channel_ids` channel.
3. The bot can **send messages and embeds** in `approval_channel_id` and `posting_channel_id`.
4. The role in `staff_role_id` exists and is assigned to the staff who approve candidates.

---

## 6. Starting the bot

```powershell
cd "C:\path\to\ClverBoardBot"
python bot.py
```

A healthy startup logs each stage in order:

```text
[<time>] [INFO    ] discord.client: logging in using static token
[<time>] [INFO    ] clverboard: Privileged intents OK (message content enabled).
[<time>] [INFO    ] clverboard: Resolving configured guild <guild id> ...
[<time>] [INFO    ] clverboard: Resolved guild: <server name> (<guild id>)
[<time>] [INFO    ] clverboard: Synced 1 command(s) to <server name> (<guild id>).
[<time>] [INFO    ] discord.gateway: Shard ID None has connected to Gateway ...
[<time>] [INFO    ] clverboard: Logged in as <bot name> - ClverBoard systems ready.
```

If a stage fails, the log line names that stage and what to check. Preconditions are
checked before the operations they gate, so a misconfiguration fails in seconds rather
than after a series of gateway reconnects.

---

## 7. Commands

| Command | Who can use it | Description |
| --- | --- | --- |
| `/clverboard-scan` | Members holding `staff_role_id` | Manually runs scan → analyze → verification. Refused if a cycle is already active. |
| **Approve** (button) | Members holding `staff_role_id` | Marks a candidate approved. |
| **Reject** (button) | Members holding `staff_role_id` | Marks a candidate rejected. |

Anyone without `staff_role_id` gets an ephemeral "You don't have permission to run this."
and the command does not execute.

Commands sync to the configured guild only, so they appear immediately rather than after
Discord's global propagation delay.

---

## 8. ClverBoard workflow

```text
Scan             collect posts with >=1 reaction from scan_channel_ids over period_days
  |
Analyze          drop posts below reaction_threshold, rank by reaction count
  |
Verification     each candidate posted to approval_channel_id with Approve/Reject buttons
  |
Delay            posting_delay_seconds once every candidate has a decision
  |
Posting          approved candidates published to posting_channel_id
```

A cycle is "active" while `data/cycle.json` exists — from the moment a scan finds
qualifying candidates until posting completes. New scans are refused while a cycle is
active, preventing duplicate processing. Published message IDs are recorded in
`data/posted_ids.json`, so a post picked up again by a later overlapping period is never
published twice. Rejected candidates are never posted.

The scheduled scan runs the same pipeline automatically once a day, but only on dates
falling inside a `cycle_trigger_days` window.

---

## 9. Common startup errors

| Error | Cause and fix |
| --- | --- |
| `ModuleNotFoundError: No module named 'discord'` | Run `pip install -r requirements.txt` with the same interpreter used for `bot.py`. |
| `Startup failed at stage 'Load Configuration': DISCORD_TOKEN is not set` | Create `.env` from `.env.example` and set a real token. |
| `Startup failed at stage 'Load Configuration': Missing config file` | Create `config.json` from `config.example.json`. |
| `... still has placeholder value(s) for: guild_id` | A `0` was never replaced in `config.json`. Set the real ID. |
| `Startup failed at stage 'Connect to Discord': the bot token was rejected` | Token is wrong or was regenerated. Update `.env`. |
| `The Message Content privileged intent is not enabled for application ...` | Enable **MESSAGE CONTENT INTENT** in the Developer Portal (section 4). The log line includes a direct link to the page. |
| `Bot '<name>' cannot see guild_id=<id>` | Wrong `guild_id`, or the bot was never invited to that server. See below. |
| `Command sync ... was refused (403 Missing Access)` | Bot is in the server but was invited without `applications.commands`. See below. |
| Slash commands don't appear in Discord | Sync succeeded but the client is stale — restart the Discord app. |

---

## Diagnosing `403 Missing Access`

Error code `50001` on `tree.sync(guild=...)` means the bot cannot act on the target
guild. Work through these in order:

**1. Is `guild_id` actually set?**

The most common cause is a `config.json` copied from the template with `"guild_id": 0`
never filled in. `0` is not a real server, so Discord rejects the sync with
`403 Missing Access`. Startup now catches this before connecting.

**2. Is `guild_id` the right server?**

Right-click your server name → **Copy Server ID** and compare. Note that a *channel* ID
is not a server ID — mixing them up produces the same error.

**3. Is the bot actually in that server?**

Check the server's member list. If the bot isn't there, it was never invited, or was
invited to a different server.

Discord returns `404 Unknown Guild` — not 403 — when the bot isn't a member, so
"wrong ID" and "not invited" look identical from the API. Check both.

**4. Was the bot invited with `applications.commands`?**

A bot invited with only the `bot` scope joins the server and logs in fine, but **cannot
register slash commands** — that specific combination is what produces `403 Missing
Access` at the sync call while everything before it succeeds. Re-invite using an OAuth2
URL with **both** `bot` and `applications.commands` (section 4). Re-inviting an existing
member bot to add a scope is safe; it does not kick or duplicate the bot.

**5. Confirm the token belongs to the expected application.**

If you maintain more than one bot application, a token from application A cannot sync
commands to a server that only has application B's bot in it. The startup log prints the
bot identity it authenticated as — verify it matches the bot in your member list.

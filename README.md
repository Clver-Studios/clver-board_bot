# ClverBoard Bot

A Discord starboard for the Clver community.

The bot looks through your channels for posts people reacted to, shows the popular ones to
your staff for approval, and publishes the approved ones to a ClverBoard channel. Nothing
gets posted publicly unless a staff member approves it first.

---

## How it works

```text
1. SCAN       Look through the chosen channels for posts from the last 15 days
                  that got at least one reaction.

2. ANALYZE    Keep only the posts that hit the reaction threshold,
                  then rank them by reaction count.

3. VERIFY     Post each one in the staff channel with Approve / Reject buttons.
                  Staff decide. Nothing moves until every post has a decision.

4. WAIT       Short delay (default ~4 minutes) after the last decision.

5. POST       Publish the approved posts to the public ClverBoard channel.
                  Rejected posts are dropped and never published.
```

This runs automatically twice a month, and a staff member can also start it by hand with
`/clverboard-scan`.

**It won't double-post.** Once a run is in progress, another one can't start until it
finishes. And every post the bot has ever published is remembered, so the same post never
appears on the board twice — even if a later scan picks it up again.

---

## Commands

| Command | Who can use it | What it does |
| --- | --- | --- |
| `/clverboard-scan` | Staff role only | Starts a scan right away |
| **Approve** button | Staff role only | Marks a post to be published |
| **Reject** button | Staff role only | Drops the post |

Anyone without the staff role gets a "you don't have permission" message that only they
can see, and nothing happens.

---

## Setup

You need **Python 3.11+**.

**1. Install the dependencies**

```sh
pip install -r requirements.txt
```

**2. Add your bot token**

Copy `.env.example` to `.env` and paste your token in:

```env
DISCORD_TOKEN=your-bot-token-here
```

**3. Add your server details**

Copy `config.example.json` to `config.json` and replace every `0` with a real ID.

To get an ID: turn on **Discord → Settings → Advanced → Developer Mode**, then right-click
a server, channel, or role and pick **Copy ID**.

| Setting | What it is |
| --- | --- |
| `guild_id` | Your server |
| `scan_channel_ids` | The channels to look through |
| `approval_channel_id` | Staff-only channel where posts get reviewed |
| `posting_channel_id` | Public channel where approved posts go |
| `staff_role_id` | The role allowed to approve and reject |
| `reaction_threshold` | How many reactions a post needs to qualify |
| `period_days` | How far back each scan looks |
| `posting_delay_seconds` | Wait time before publishing |

**4. Set up the bot on Discord's side**

In the [Developer Portal](https://discord.com/developers/applications), open your app:

* Under **Bot → Privileged Gateway Intents**, turn on **MESSAGE CONTENT INTENT**.
  The bot needs this to read what posts actually say. (Presence and Server Members are
  not needed — leave them off.)
* Under **OAuth2 → URL Generator**, tick **both** `bot` and `applications.commands`, then
  give it: View Channels, Read Message History, Send Messages, Embed Links.
* Open the generated link and invite the bot to your server.

**5. Start it**

```sh
python bot.py
```

You should see:

```text
[INFO] clverboard: Privileged intents OK (message content enabled).
[INFO] clverboard: Resolved guild: <your server>
[INFO] clverboard: Synced 1 command(s) to <your server>
[INFO] clverboard: Logged in as <bot name> - ClverBoard systems ready.
```

If something is wrong, the bot tells you which step failed and what to check, instead of
crashing with a confusing error.

---

## If something goes wrong

| What you see | What it means |
| --- | --- |
| `still has placeholder value(s) for: guild_id` | You left a `0` in `config.json`. Put the real ID in. |
| `Message Content privileged intent is not enabled` | Turn it on in the Developer Portal (step 4). |
| `cannot see guild_id=...` | Wrong server ID, or the bot was never invited to that server. |
| `Command sync ... 403 Missing Access` | Bot was invited without `applications.commands`. Re-invite it with both scopes. |
| `DISCORD_TOKEN is not set` | Missing or empty `.env`. |
| Slash command doesn't show up | It synced fine — restart your Discord app to refresh. |
| `PyNaCl is not installed` warning | Harmless. That's for voice, which this bot doesn't use. |

More detail is in [SETUP.md](SETUP.md). Past bugs and their fixes are in [FIXLOG.md](FIXLOG.md).

---

## A note on your token

`.env` and `config.json` hold your bot token and server IDs. Both are listed in
`.gitignore`, so they stay on your machine and never get uploaded. Keep it that way — a
leaked bot token lets anyone control your bot.

The `.example` versions of both files are safe to share, which is why those are the ones
in this repo.

---

## Project layout

```text
bot.py                  Starts the bot and checks everything is configured properly
core/
  config.py             Loads and validates .env + config.json
  scan_service.py       Step 1 - collects posts
  analyze_service.py    Step 2 - filters and ranks them
  storage.py            Remembers the current run and what's already been posted
  embeds.py             Builds the message cards
cogs/
  scanning.py           The /clverboard-scan command and the twice-monthly schedule
  verification.py       Approve / Reject buttons
  posting.py            Publishes approved posts after the delay
```

Each step is kept separate so any one of them can be changed or tested on its own.

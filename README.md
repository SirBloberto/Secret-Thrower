# Secret Thrower

A Discord bot for a social deduction game played across two voice channel teams. One or more players on each team are secretly assigned as "throwers" — their goal is to make their team lose without being detected. After the match, players vote on who they think the thrower was.

## Game Loop

1. **`/game setup`** — Start a game by selecting two voice channels as teams. Players currently in those channels are pulled in automatically.
2. **`/game add` / `/game remove`** — Adjust the player list before the game begins.
3. **`/game start`** — Secretly assigns throwers on each team and DMs them their role. Thrower selection is weighted so players who haven't thrown recently are more likely to be chosen.
4. Play the game.
5. **`/game result`** — Declare the winning team and open the voting phase. The bot reacts to the game embed with one emoji per player — letters for team 1, numbers for team 2. Players add the matching reaction to accuse who they think the thrower was, one vote per team. Voting closes automatically when the timer runs out.
6. Results are revealed: throwers are unmasked, vote tallies are shown, and caught/escaped status is displayed. The game record is saved and ELO is updated.

## Commands

### Game Management

| Command | Arguments | Description |
|---|---|---|
| `/game setup` | `team1`, `team2` | Initialize a game from two voice channels |
| `/game add` | `team`, `user` | Add or move a player to a team |
| `/game remove` | `user` | Remove a player from the game |
| `/game start` | `team1_count?`, `team2_count?` | Assign throwers and begin the game |
| `/game result` | `winner` | Declare the winning team and start voting |
| `/game cancel` | — | Cancel the current game |

### Profile

| Command | Arguments | Description |
|---|---|---|
| `/profile stats` | `user?` | View game statistics and ELO for yourself or another player |
| `/profile leaderboard` | — | Show top players ranked by various stats |

### General

| Command | Arguments | Description |
|---|---|---|
| `/help` | — | Show available commands |

## Settings

Settings are per game, not per server. After `/game setup`, the game host or a server moderator opens the ⚙️ **Game Settings** button on the game embed.

| Setting | Default | Description |
|---|---|---|
| Voting timer | `60` | Seconds players have to vote after a result is declared (minimum 10) |
| Thrower info | `off` | If enabled, throwers are told the names of any thrower teammates |

## Rating

Every player carries two ratings on a 0–100 scale, both starting at 50:

- **Innocent ELO** — 60% whether your team won, 40% how accurately you voted relative to the rest of the game.
- **Thrower ELO** — outcome based, ranked best to worst: your team lost and you were not the most accused player, your team won and you stayed hidden, your team lost but you were identified, your team won and you were caught.

Both use an asymmetric K factor, so gaining rating is easier below 50 and harder above it.

## Hosting

### Environment Variables

```env
DISCORD_TOKEN=discord_bot_token
DATABASE_URL=postgresql://user:password@host:port/dbname
SUPPORT_URL=https://discord.gg/your-support-server
SUPPORT_DISCORD=support_discord_user_id
REDIS_HOST=redis
REDIS_PORT=6379
```

`DISCORD_TOKEN` and `DATABASE_URL` are required. `SUPPORT_URL` and `SUPPORT_DISCORD` are optional and only change the footer of `/help`. `REDIS_HOST` and `REDIS_PORT` default to `redis` and `6379`, which is what Docker Compose provides.

### Running with Docker

```bash
docker-compose up --build -d
```

Migrations run automatically on startup.

### Running Locally (Development)

```bash
uv sync
alembic upgrade head
python bot.py
```

### Tests and Linting

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

### Recomputing Ratings

If the scoring formula in `elo.py` changes, replay every recorded game through it and rewrite all stored ratings:

```bash
uv run python -m scripts.backfill_elo
```

## Layout

| Path | Purpose |
|---|---|
| `bot.py` | Entry point; loads every cog in `cogs/` |
| `cogs/game.py` | Game lifecycle commands, restart recovery, voting and results |
| `cogs/profile.py` | Stats and leaderboard commands |
| `cogs/general.py` | `/help` and the database keepalive task |
| `elo.py` | Rating math — pure functions, the single source of truth for scoring |
| `data.py` | In-memory game state and its Redis serialisation |
| `models.py` | SQLAlchemy tables |
| `database.py` | Engine, session factory and Redis game-state helpers |
| `scripts/` | One-off maintenance scripts |

## Requirements

- Python 3.12+
- PostgreSQL (or a Supabase project)
- Redis
